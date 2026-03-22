"""MindosScheduler — passive periodic task engine.

No background threads/processes. Checks are triggered by:
  - Ome App launch
  - HTTP Server heartbeat
  - CLI `mindos maintenance`
  - Any call to check_and_run()

Each job has a minimum interval. If enough time has passed since last run,
the job executes. Results are emitted to EventBus.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from mindos.core import Mindos
    from mindos.event_bus import EventBus

log = logging.getLogger("mindos.scheduler")


@dataclass
class JobResult:
    """Result of a scheduled job execution."""
    name: str
    success: bool
    data: dict[str, Any]
    duration_ms: float
    executed_at: float


class MindosScheduler:
    """Passive periodic task engine for Mindos maintenance."""

    # Default job definitions: name → (interval_hours, method_name_on_mindos)
    DEFAULT_JOBS = [
        {"name": "daily_reflect", "interval_hours": 24, "method": "reflect"},
        {"name": "memory_compress", "interval_hours": 72, "method": "_run_compress"},
        {"name": "daily_digest", "interval_hours": 24, "method": "_run_daily_digest"},
        {"name": "weekly_insight", "interval_hours": 168, "method": "_run_weekly_insight"},
        {"name": "stale_cleanup", "interval_hours": 168, "method": "_run_stale_cleanup"},
        {"name": "redundant_merge", "interval_hours": 72, "method": "_run_redundant_merge"},
    ]

    def __init__(self, mindos: "Mindos", event_bus: Optional["EventBus"] = None) -> None:
        self.mindos = mindos
        self.bus = event_bus
        self._last_run: dict[str, float] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load last-run timestamps from soul_state."""
        raw = self.mindos.store.get_state("scheduler_last_run")
        if raw:
            try:
                self._last_run = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    def _save_state(self) -> None:
        """Persist last-run timestamps."""
        self.mindos.store.set_state("scheduler_last_run", json.dumps(self._last_run))

    def check_and_run(self) -> list[JobResult]:
        """Check all jobs, run any that are due. Returns list of executed job results."""
        now = time.time()
        results: list[JobResult] = []

        for job in self.DEFAULT_JOBS:
            name = job["name"]
            interval = job["interval_hours"] * 3600
            last = self._last_run.get(name, 0)

            if now - last < interval:
                continue

            result = self._run_job(job, now)
            results.append(result)
            self._last_run[name] = now

        if results:
            self._save_state()
            if self.bus:
                from mindos.event_bus import MAINTENANCE_RUN
                self.bus.emit(MAINTENANCE_RUN, {
                    "jobs_run": len(results),
                    "job_names": [r.name for r in results],
                })

        return results

    def force_run(self, job_name: str) -> Optional[JobResult]:
        """Force-run a specific job regardless of interval."""
        for job in self.DEFAULT_JOBS:
            if job["name"] == job_name:
                result = self._run_job(job, time.time())
                self._last_run[job_name] = time.time()
                self._save_state()
                return result
        return None

    def job_status(self) -> list[dict[str, Any]]:
        """Get status of all jobs: name, last_run, next_due, overdue."""
        now = time.time()
        status = []
        for job in self.DEFAULT_JOBS:
            name = job["name"]
            last = self._last_run.get(name, 0)
            interval = job["interval_hours"] * 3600
            next_due = last + interval if last else 0
            status.append({
                "name": name,
                "interval_hours": job["interval_hours"],
                "last_run": last,
                "next_due": next_due,
                "overdue": now > next_due,
            })
        return status

    def _run_job(self, job: dict, now: float) -> JobResult:
        """Execute a single job."""
        name = job["name"]
        method_name = job["method"]
        start = time.time()

        try:
            # Look for method on scheduler first, then on mindos
            method: Optional[Callable] = getattr(self, method_name, None)
            if method is None:
                method = getattr(self.mindos, method_name, None)
            if method is None:
                return JobResult(name=name, success=False,
                                 data={"error": f"method {method_name} not found"},
                                 duration_ms=0, executed_at=now)

            result_data = method()
            duration = (time.time() - start) * 1000
            log.info("Scheduler: %s completed in %.1fms", name, duration)
            return JobResult(
                name=name, success=True,
                data=result_data if isinstance(result_data, dict) else {"result": str(result_data)},
                duration_ms=duration, executed_at=now,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            log.warning("Scheduler: %s failed: %s", name, e)
            return JobResult(
                name=name, success=False,
                data={"error": str(e)},
                duration_ms=duration, executed_at=now,
            )

    # -- built-in job methods --------------------------------------------------

    def _run_compress(self) -> dict[str, Any]:
        """Compress old episodes."""
        return self.mindos.store.compress_old_episodes(older_than_days=90)

    def _run_daily_digest(self) -> dict[str, Any]:
        """Generate daily digest via InsightEngine."""
        from mindos.insight import InsightEngine
        engine = InsightEngine(self.mindos.store)
        digest = engine.daily_digest(hours=24)
        if self.bus:
            from mindos.event_bus import INSIGHT_GENERATED
            self.bus.emit(INSIGHT_GENERATED, {"type": "daily_digest", "digest": digest})
        return digest

    def _run_weekly_insight(self) -> dict[str, Any]:
        """Generate weekly summary via InsightEngine."""
        from mindos.insight import InsightEngine
        engine = InsightEngine(self.mindos.store)
        summary = engine.weekly_summary()
        if self.bus:
            from mindos.event_bus import INSIGHT_GENERATED
            self.bus.emit(INSIGHT_GENERATED, {"type": "weekly_summary", "summary": summary})
        return summary

    def _run_stale_cleanup(self) -> dict[str, Any]:
        """Archive stale memories."""
        return self.mindos.store.archive_stale(inactive_days=180, min_access=2)

    def _run_redundant_merge(self) -> dict[str, Any]:
        """Merge redundant facts."""
        return self.mindos.store.merge_redundant_facts(similarity_threshold=0.8)
