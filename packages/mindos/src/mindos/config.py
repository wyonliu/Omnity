"""Mindos configuration: config.yaml loading + ModelRouter.

Supports provider types:
  - openai_compatible: Any OpenAI-API-compatible endpoint (OpenAI, DeepSeek, etc.)
  - anthropic: Native Anthropic Messages API via anthropic SDK
  - ollama: Local Ollama instance (no API key required)
  - passthrough: Stub for testing
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

log = logging.getLogger("mindos.config")


@dataclass
class ModelProvider:
    name: str
    type: str           # openai_compatible | anthropic | ollama | passthrough
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""
    priority: int = 99
    for_tasks: list[str] = field(default_factory=list)
    max_tokens: int = 1024

    @property
    def api_key(self) -> str:
        if self.api_key_env:
            return os.environ.get(self.api_key_env, "")
        return ""

    @property
    def available(self) -> bool:
        if self.type == "passthrough":
            return True
        if self.type == "ollama":
            return True  # assume local ollama is running
        return bool(self.api_key)


_DEFAULT_CONFIG: dict[str, Any] = {
    "models": [
        {
            "name": "deepseek",
            "type": "openai_compatible",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
            "model": "deepseek-chat",
            "priority": 1,
            "for": ["chat", "commit_digest", "reflection", "reasoning"],
        },
        {
            "name": "openai",
            "type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-4o-mini",
            "priority": 2,
            "for": ["commit_digest", "reflection", "reasoning", "creation"],
        },
        {
            "name": "anthropic",
            "type": "anthropic",
            "api_key_env": "ANTHROPIC_API_KEY",
            "model": "claude-sonnet-4-20250514",
            "priority": 3,
            "for": ["deep_reasoning", "complex_creation"],
        },
    ],
    "fallback": "deepseek",
    "hydrate": {
        "default_max_tokens": 2000,
        "include_relations": True,
        "include_capabilities": True,
    },
    "commit": {
        "use_llm": True,
        "fallback_to_rules": True,
    },
    "reflection": {
        "trigger_every_n_commits": 20,
        "enabled": True,
    },
}


class MindosConfig:
    """Loads and manages ~/.mindos/config.yaml."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._providers: list[ModelProvider] = []
        self._parse_models()

    @classmethod
    def load(cls, root: Path) -> "MindosConfig":
        cfg_path = root / "config.yaml"
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            if yaml:
                data = yaml.safe_load(text) or {}
            else:
                import json
                data = json.loads(text)
            merged = {**_DEFAULT_CONFIG, **data}
            return cls(merged)
        else:
            # No config.yaml — auto-detect from environment variables
            instance = cls.from_env()
            cls._write_config(cfg_path, instance._data)
            return instance

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MindosConfig":
        """Create config programmatically from a dict — no file needed.

        Example:
            cfg = MindosConfig.from_dict({
                "models": [{"name": "ds", "type": "openai_compatible",
                            "base_url": "https://api.deepseek.com",
                            "api_key_env": "DEEPSEEK_API_KEY",
                            "model": "deepseek-chat"}],
            })
        """
        merged = {**_DEFAULT_CONFIG, **data}
        return cls(merged)

    @classmethod
    def from_env(cls) -> "MindosConfig":
        """Auto-detect available LLM providers from environment variables.

        Checks: OPENROUTER_API_KEY, DEEPSEEK_API_KEY, OPENAI_API_KEY,
                ANTHROPIC_API_KEY, and Ollama at localhost:11434.
        Returns a config with all detected providers, prioritized by quality.
        """
        models: list[dict[str, Any]] = []
        priority = 1

        if os.environ.get("OPENROUTER_API_KEY"):
            models.append({
                "name": "openrouter", "type": "openai_compatible",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "model": "deepseek/deepseek-chat",
                "priority": priority,
                "for": ["chat", "commit_digest", "reflection", "reasoning"],
            })
            priority += 1

        if os.environ.get("DEEPSEEK_API_KEY"):
            models.append({
                "name": "deepseek", "type": "openai_compatible",
                "base_url": "https://api.deepseek.com",
                "api_key_env": "DEEPSEEK_API_KEY",
                "model": "deepseek-chat",
                "priority": priority,
                "for": ["chat", "commit_digest", "reflection", "reasoning"],
            })
            priority += 1

        if os.environ.get("OPENAI_API_KEY"):
            models.append({
                "name": "openai", "type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-4o-mini",
                "priority": priority,
                "for": ["chat", "commit_digest", "reflection", "reasoning"],
            })
            priority += 1

        if os.environ.get("ANTHROPIC_API_KEY"):
            models.append({
                "name": "anthropic", "type": "anthropic",
                "api_key_env": "ANTHROPIC_API_KEY",
                "model": "claude-sonnet-4-20250514",
                "priority": priority,
                "for": ["deep_reasoning", "complex_creation"],
            })
            priority += 1

        # Ollama as lowest-priority fallback (always available if running)
        models.append({
            "name": "ollama", "type": "ollama",
            "model": "qwen3.5:14b",
            "priority": priority,
            "for": [],  # catch-all fallback
        })

        fallback = models[0]["name"] if models else "ollama"
        data = {**_DEFAULT_CONFIG, "models": models, "fallback": fallback}
        return cls(data)

    @classmethod
    def _write_config(cls, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if yaml:
            path.write_text(
                yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
                encoding="utf-8",
            )
        else:
            import json
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _parse_models(self) -> None:
        for m in self._data.get("models", []):
            self._providers.append(ModelProvider(
                name=m["name"], type=m["type"], model=m.get("model", ""),
                base_url=m.get("base_url", ""), api_key_env=m.get("api_key_env", ""),
                priority=m.get("priority", 99), for_tasks=m.get("for", []),
                max_tokens=m.get("max_tokens", 1024),
            ))
        self._providers.sort(key=lambda p: p.priority)

    @property
    def providers(self) -> list[ModelProvider]:
        return self._providers

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        d = self._data
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
            if d is None:
                return default
        return d


class ModelRouter:
    """Select the best available LLM provider for a given task.

    Supports:
      - openai_compatible: OpenAI, DeepSeek, etc. (via openai SDK)
      - anthropic: Native Anthropic Messages API (via anthropic SDK)
      - ollama: Local Ollama instance (via OpenAI-compatible endpoint)
    """

    def __init__(self, config: MindosConfig) -> None:
        self.config = config
        self._cache: dict[str, tuple[float, str]] = {}  # hash → (timestamp, response)
        self._cache_ttl = 300  # 5 minutes

    def select(self, task: str = "reasoning") -> Optional[ModelProvider]:
        for p in self.config.providers:
            if not p.available:
                continue
            if task in p.for_tasks or not p.for_tasks:
                return p
        fb_name = self.config.get("fallback")
        if fb_name:
            for p in self.config.providers:
                if p.name == fb_name and p.available:
                    return p
        return None

    def _select_candidates(self, task: str) -> list[ModelProvider]:
        """Return all available providers for a task, in priority order."""
        candidates = []
        for p in self.config.providers:
            if not p.available:
                continue
            if task in p.for_tasks or not p.for_tasks:
                candidates.append(p)
        # Add fallback if not already included
        fb_name = self.config.get("fallback")
        if fb_name:
            fb_names = {c.name for c in candidates}
            if fb_name not in fb_names:
                for p in self.config.providers:
                    if p.name == fb_name and p.available:
                        candidates.append(p)
                        break
        return candidates

    def call_llm(self, system: str, user: str, task: str = "reasoning",
                 max_tokens: int = 1024, json_mode: bool = False,
                 use_cache: bool = False, timeout: float = 30.0) -> Optional[str]:
        """Call the best available LLM with automatic fallback.

        Tries providers in priority order. If one fails (timeout, error),
        automatically falls through to the next available provider.

        Args:
            timeout: Per-provider timeout in seconds (default 30s).
        """
        candidates = self._select_candidates(task)
        if not candidates:
            if not getattr(self, "_warned_tasks", None):
                self._warned_tasks = set()
            if task not in self._warned_tasks:
                log.warning("No available provider for task=%s (this warning shown once per task)", task)
                self._warned_tasks.add(task)
            return None

        # Check cache (keyed on first candidate)
        if use_cache:
            cache_key = hashlib.md5(
                f"{candidates[0].name}:{system}:{user}:{max_tokens}:{json_mode}".encode()
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                log.debug("Cache hit for task=%s provider=%s", task, candidates[0].name)
                return cached[1]
        else:
            cache_key = ""

        # Try each provider in order; fall through on failure
        last_error: Optional[Exception] = None
        for provider in candidates:
            log.debug("Trying LLM: provider=%s model=%s task=%s", provider.name, provider.model, task)
            try:
                result: Optional[str] = None
                if provider.type == "anthropic":
                    result = self._call_anthropic(provider, system, user, max_tokens, json_mode, timeout)
                elif provider.type == "ollama":
                    result = self._call_ollama(provider, system, user, max_tokens, json_mode, timeout)
                elif provider.type == "openai_compatible":
                    result = self._call_openai_compat(provider, system, user, max_tokens, json_mode, timeout)

                if result is not None:
                    if use_cache and cache_key:
                        self._cache[cache_key] = (time.time(), result)
                        if len(self._cache) > 100:
                            cutoff = time.time() - self._cache_ttl
                            self._cache = {k: v for k, v in self._cache.items() if v[0] > cutoff}
                    return result
                # result is None but no exception — provider returned empty
                log.warning("Provider %s returned empty result for task=%s, trying next", provider.name, task)
            except Exception as e:
                last_error = e
                log.warning("Provider %s failed for task=%s: %s — trying next", provider.name, task, e)
                continue

        log.error("All %d providers failed for task=%s. Last error: %s", len(candidates), task, last_error)
        return None

    def _call_openai_compat(self, provider: ModelProvider, system: str, user: str,
                            max_tokens: int, json_mode: bool,
                            timeout: float = 30.0) -> Optional[str]:
        try:
            import openai
        except ImportError:
            log.warning("openai package not installed, cannot use provider %s", provider.name)
            return None

        kwargs: dict[str, Any] = {"timeout": timeout}
        if provider.base_url:
            kwargs["base_url"] = provider.base_url

        client = openai.OpenAI(api_key=provider.api_key, **kwargs)
        req: dict[str, Any] = {
            "model": provider.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            req["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**req)
        text = resp.choices[0].message.content
        return text.strip() if text else None

    def _call_anthropic(self, provider: ModelProvider, system: str, user: str,
                        max_tokens: int, json_mode: bool,
                        timeout: float = 30.0) -> Optional[str]:
        """Native Anthropic Messages API call."""
        try:
            import anthropic
        except ImportError:
            log.warning("anthropic package not installed, cannot use provider %s", provider.name)
            return None

        client = anthropic.Anthropic(api_key=provider.api_key, timeout=timeout)
        resp = client.messages.create(
            model=provider.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text
        return text.strip() if text else None

    def _call_ollama(self, provider: ModelProvider, system: str, user: str,
                     max_tokens: int, json_mode: bool,
                     timeout: float = 30.0) -> Optional[str]:
        """Call local Ollama via its OpenAI-compatible endpoint."""
        try:
            import openai
        except ImportError:
            log.warning("openai package not installed, cannot use Ollama provider %s", provider.name)
            return None

        base_url = provider.base_url or "http://localhost:11434/v1"
        client = openai.OpenAI(api_key="ollama", base_url=base_url, timeout=timeout)
        req: dict[str, Any] = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if max_tokens:
            req["max_tokens"] = max_tokens
        if json_mode:
            req["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**req)
        text = resp.choices[0].message.content
        return text.strip() if text else None
