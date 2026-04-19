"""Overnight Soul Sync — nightly batch that keeps a Mindos sharp.

Why not "sleep-time compute"?  Because Letta shipped a product under that
name (2025-09). We're not reselling a Letta brand; we run an offline pass
that merges duplicates, archives stale memories, compresses ancient
episodes, and writes one or more reflection breadcrumbs to EvoLog. Same
spirit, different scope.

What one run does (in order):

    1. consolidate        — merge near-duplicate memories
    2. merge_facts        — dedupe fact entries at a higher threshold
    3. compress_episodes  — collapse old episodes into summaries
    4. archive_stale      — park long-unused memories (still recoverable)
    5. reflect            — optional LLM pass; skipped offline / no API key
    6. record_evo         — one ``overnight_sync`` row with per-step counts

Every step is a no-op if the required method isn't available on the store,
so this works against PG+RLS stores that implement a subset. Nothing here
calls out to a remote model unless the caller passes ``enable_reflection=True``
**and** the Mindos was wired with a reflection-capable layer.

Safety:
- ``dry_run=True`` runs every step with zero mutations — a preview.
- All mutations are caught per-step and logged — one failing step never
  kills the whole pass.
- Each pass records a single EvoLog row for auditability.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger("mindos.harness.overnight")


# --- config ---------------------------------------------------------------

@dataclass
class OvernightConfig:
    consolidate_threshold: float = 0.92
    merge_facts_threshold: float = 0.97
    compress_older_than_days: int = 30
    archive_inactive_days: int = 90
    archive_min_access: int = 2
    enable_reflection: bool = False
    # Step allowlist — None means "run all". Useful for testing.
    only: Optional[set[str]] = None


@dataclass
class StepReport:
    name: str
    ok: bool = True
    error: Optional[str] = None
    counts: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class OvernightReport:
    started_at: float = 0.0
    finished_at: float = 0.0
    dry_run: bool = False
    steps: list[StepReport] = field(default_factory=list)
    evo_log_id: Optional[str] = None

    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.started_at) * 1000)

    def totals(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.steps:
            for k, v in (s.counts or {}).items():
                out[k] = out.get(k, 0) + int(v)
        return out

    def ok(self) -> bool:
        return all(s.ok or s.skipped for s in self.steps)


# --- sync orchestrator ----------------------------------------------------

class OvernightSoulSync:
    """Run one nightly pass over a Mindos instance."""

    STEP_NAMES = (
        "consolidate",
        "merge_facts",
        "compress_episodes",
        "archive_stale",
        "reflect",
    )

    def __init__(
        self,
        mindos: Any,
        *,
        config: Optional[OvernightConfig] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        self.mindos = mindos
        self.store = getattr(mindos, "store", None)
        self.config = config or OvernightConfig()
        self.on_event = on_event or (lambda kind, payload: None)

    # -- public ---------------------------------------------------------

    def run(self, *, dry_run: bool = False) -> OvernightReport:
        report = OvernightReport(started_at=time.time(), dry_run=dry_run)
        self._emit("overnight_started", {"dry_run": dry_run})

        for name in self.STEP_NAMES:
            if self.config.only is not None and name not in self.config.only:
                report.steps.append(StepReport(name=name, skipped=True,
                                               skip_reason="not in allowlist"))
                continue
            report.steps.append(self._run_step(name, dry_run=dry_run))

        report.finished_at = time.time()

        # Record one evolog row — even on partial failure
        report.evo_log_id = self._record_evo(report)
        self._emit("overnight_finished", {
            "duration_ms": report.duration_ms,
            "totals": report.totals(),
            "ok": report.ok(),
        })
        return report

    # -- per-step -------------------------------------------------------

    def _run_step(self, name: str, *, dry_run: bool) -> StepReport:
        t0 = time.time()
        try:
            if name == "consolidate":
                counts = self._step_consolidate(dry_run=dry_run)
            elif name == "merge_facts":
                counts = self._step_merge_facts(dry_run=dry_run)
            elif name == "compress_episodes":
                counts = self._step_compress_episodes(dry_run=dry_run)
            elif name == "archive_stale":
                counts = self._step_archive_stale(dry_run=dry_run)
            elif name == "reflect":
                counts = self._step_reflect(dry_run=dry_run)
            else:
                return StepReport(name=name, skipped=True,
                                  skip_reason=f"unknown step {name}")
        except Exception as e:
            log.exception("overnight step %s failed", name)
            return StepReport(
                name=name, ok=False,
                error=f"{type(e).__name__}: {e}",
                duration_ms=int((time.time() - t0) * 1000),
            )
        return StepReport(
            name=name, ok=True, counts=counts,
            duration_ms=int((time.time() - t0) * 1000),
        )

    def _step_consolidate(self, *, dry_run: bool) -> dict[str, int]:
        if not hasattr(self.store, "consolidate"):
            return {"skipped": 1}
        if dry_run:
            return {"would_merge": 0}  # consolidate() has no dry-run mode
        result = self.store.consolidate(
            similarity_threshold=self.config.consolidate_threshold) or {}
        return _coerce_counts(result)

    def _step_merge_facts(self, *, dry_run: bool) -> dict[str, int]:
        if not hasattr(self.store, "merge_redundant_facts"):
            return {"skipped": 1}
        if dry_run:
            return {"would_merge": 0}
        result = self.store.merge_redundant_facts(
            similarity_threshold=self.config.merge_facts_threshold) or {}
        return _coerce_counts(result)

    def _step_compress_episodes(self, *, dry_run: bool) -> dict[str, int]:
        if not hasattr(self.store, "compress_old_episodes"):
            return {"skipped": 1}
        if dry_run:
            return {"would_compress": 0}
        result = self.store.compress_old_episodes(
            older_than_days=self.config.compress_older_than_days) or {}
        return _coerce_counts(result)

    def _step_archive_stale(self, *, dry_run: bool) -> dict[str, int]:
        if not hasattr(self.store, "archive_stale"):
            return {"skipped": 1}
        if dry_run:
            return {"would_archive": 0}
        result = self.store.archive_stale(
            inactive_days=self.config.archive_inactive_days,
            min_access=self.config.archive_min_access) or {}
        return _coerce_counts(result)

    def _step_reflect(self, *, dry_run: bool) -> dict[str, int]:
        if not self.config.enable_reflection:
            return {"skipped": 1}
        reflect = getattr(self.mindos, "reflect", None)
        if not callable(reflect):
            return {"skipped": 1}
        if dry_run:
            return {"would_reflect": 1}
        # Some .reflect() signatures differ; keep it simple.
        try:
            reflect()
        except TypeError:
            # older signatures may need layer kw — skip for safety
            return {"skipped": 1}
        return {"reflected": 1}

    # -- evolog ---------------------------------------------------------

    def _record_evo(self, report: OvernightReport) -> Optional[str]:
        if not self.store or not hasattr(self.store, "record_evo"):
            return None
        summary = (
            f"overnight sync ({'dry-run' if report.dry_run else 'live'}): "
            f"{report.duration_ms}ms, "
            + ", ".join(f"{k}={v}" for k, v in sorted(report.totals().items()))
        )
        details = {
            "dry_run": report.dry_run,
            "duration_ms": report.duration_ms,
            "steps": [
                {
                    "name": s.name, "ok": s.ok, "skipped": s.skipped,
                    "counts": s.counts, "error": s.error,
                    "duration_ms": s.duration_ms,
                } for s in report.steps
            ],
        }
        try:
            return self.store.record_evo(
                event_type="overnight_sync",
                summary=summary[:500],
                layer="L4",
                details=details,
            )
        except Exception as e:
            log.warning("record_evo failed: %s", e)
            return None

    # -- helpers --------------------------------------------------------

    def _emit(self, kind: str, payload: dict) -> None:
        try:
            self.on_event(kind, payload)
        except Exception:  # observer must never break the run
            log.debug("on_event raised; swallowed")


def _coerce_counts(result: Any) -> dict[str, int]:
    """Turn whatever the store returned into {str: int}."""
    if isinstance(result, dict):
        return {str(k): int(v) for k, v in result.items()
                if isinstance(v, (int, float, bool))}
    if isinstance(result, (int, float)):
        return {"count": int(result)}
    return {}
