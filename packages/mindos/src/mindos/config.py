"""Mindos configuration: config.yaml loading + ModelRouter."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


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
            "for": ["commit_digest", "reflection", "reasoning"],
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
        else:
            data = dict(_DEFAULT_CONFIG)
            cls._write_default(cfg_path)
        merged = {**_DEFAULT_CONFIG, **data}
        return cls(merged)

    @classmethod
    def _write_default(cls, path: Path) -> None:
        if yaml:
            path.write_text(
                yaml.dump(_DEFAULT_CONFIG, allow_unicode=True, sort_keys=False, default_flow_style=False),
                encoding="utf-8",
            )
        else:
            import json
            path.write_text(json.dumps(_DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")

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
    """Select the best available LLM provider for a given task."""

    def __init__(self, config: MindosConfig) -> None:
        self.config = config

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

    def call_llm(self, system: str, user: str, task: str = "reasoning",
                 max_tokens: int = 1024, json_mode: bool = False) -> Optional[str]:
        """Call the best available LLM. Returns response text or None."""
        provider = self.select(task)
        if provider is None:
            return None

        if provider.type in ("openai_compatible", "anthropic"):
            return self._call_openai_compat(provider, system, user, max_tokens, json_mode)
        return None

    def _call_openai_compat(self, provider: ModelProvider, system: str, user: str,
                            max_tokens: int, json_mode: bool) -> Optional[str]:
        try:
            import openai
        except ImportError:
            return None

        kwargs: dict[str, Any] = {}
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

        try:
            resp = client.chat.completions.create(**req)
            return resp.choices[0].message.content.strip()
        except Exception:
            return None
