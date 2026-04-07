"""Tests for MindosConfig and ModelRouter — from_dict, from_env, fallback chain, timeout."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.config import MindosConfig, ModelRouter, ModelProvider


# ── MindosConfig.from_dict ──────────────────────────────────────────

class TestFromDict:
    def test_basic(self):
        cfg = MindosConfig.from_dict({
            "models": [{
                "name": "test", "type": "passthrough",
                "model": "test-model", "priority": 1,
                "for": ["chat"],
            }],
        })
        assert len(cfg.providers) >= 1
        assert cfg.providers[0].name == "test"

    def test_merges_defaults(self):
        cfg = MindosConfig.from_dict({"models": []})
        # Should still have default config values
        assert cfg.get("fallback") == "deepseek"
        assert cfg.get("hydrate.default_max_tokens") == 2000

    def test_override_defaults(self):
        cfg = MindosConfig.from_dict({
            "models": [{"name": "x", "type": "passthrough", "model": "x"}],
            "fallback": "x",
        })
        assert cfg.get("fallback") == "x"

    def test_no_file_needed(self):
        """from_dict should not touch the filesystem."""
        cfg = MindosConfig.from_dict({"models": []})
        assert cfg is not None


# ── MindosConfig.from_env ───────────────────────────────────────────

class TestFromEnv:
    def test_detects_deepseek(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}, clear=False):
            cfg = MindosConfig.from_env()
            names = [p.name for p in cfg.providers]
            assert "deepseek" in names

    def test_detects_openrouter(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
            cfg = MindosConfig.from_env()
            names = [p.name for p in cfg.providers]
            assert "openrouter" in names

    def test_always_has_ollama_fallback(self):
        with patch.dict(os.environ, {}, clear=False):
            cfg = MindosConfig.from_env()
            names = [p.name for p in cfg.providers]
            assert "ollama" in names

    def test_priority_order(self):
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "sk-or",
            "DEEPSEEK_API_KEY": "sk-ds",
        }, clear=False):
            cfg = MindosConfig.from_env()
            # openrouter should be higher priority (lower number) than deepseek
            or_p = next(p for p in cfg.providers if p.name == "openrouter")
            ds_p = next(p for p in cfg.providers if p.name == "deepseek")
            assert or_p.priority < ds_p.priority


# ── ModelProvider ───────────────────────────────────────────────────

class TestModelProvider:
    def test_passthrough_always_available(self):
        p = ModelProvider(name="t", type="passthrough", model="t")
        assert p.available is True

    def test_ollama_always_available(self):
        p = ModelProvider(name="t", type="ollama", model="qwen3.5:14b")
        assert p.available is True

    def test_openai_needs_key(self):
        p = ModelProvider(name="t", type="openai_compatible",
                          model="gpt-4o-mini", api_key_env="NONEXISTENT_KEY_XYZ")
        assert p.available is False

    def test_openai_has_key(self):
        with patch.dict(os.environ, {"TEST_KEY_ABC": "sk-123"}):
            p = ModelProvider(name="t", type="openai_compatible",
                              model="gpt-4o-mini", api_key_env="TEST_KEY_ABC")
            assert p.available is True


# ── ModelRouter.select / _select_candidates ─────────────────────────

class TestRouterSelect:
    def _make_router(self, providers_data: list[dict]) -> ModelRouter:
        cfg = MindosConfig.from_dict({"models": providers_data, "fallback": "fb"})
        return ModelRouter(cfg)

    def test_select_by_task(self):
        r = self._make_router([
            {"name": "a", "type": "passthrough", "model": "a", "priority": 1, "for": ["chat"]},
            {"name": "b", "type": "passthrough", "model": "b", "priority": 2, "for": ["reasoning"]},
        ])
        assert r.select("chat").name == "a"
        assert r.select("reasoning").name == "b"

    def test_select_catchall(self):
        r = self._make_router([
            {"name": "specific", "type": "passthrough", "model": "s", "priority": 2, "for": ["chat"]},
            {"name": "catchall", "type": "passthrough", "model": "c", "priority": 1, "for": []},
        ])
        # catchall has higher priority and empty for_tasks
        assert r.select("anything").name == "catchall"

    def test_candidates_includes_fallback(self):
        cfg = MindosConfig.from_dict({
            "models": [
                {"name": "a", "type": "passthrough", "model": "a", "priority": 1, "for": ["chat"]},
                {"name": "fb", "type": "passthrough", "model": "fb", "priority": 99, "for": ["other"]},
            ],
            "fallback": "fb",
        })
        r = ModelRouter(cfg)
        candidates = r._select_candidates("chat")
        names = [c.name for c in candidates]
        assert "a" in names
        assert "fb" in names  # fallback appended even though task doesn't match


# ── ModelRouter.call_llm fallback chain ─────────────────────────────

class TestRouterFallback:
    def test_fallback_on_failure(self):
        """If provider A throws, should try provider B."""
        cfg = MindosConfig.from_dict({
            "models": [
                {"name": "fail", "type": "passthrough", "model": "f", "priority": 1, "for": []},
                {"name": "ok", "type": "passthrough", "model": "o", "priority": 2, "for": []},
            ],
        })
        r = ModelRouter(cfg)
        call_count = {"n": 0}

        def mock_call(provider, system, user, max_tokens, json_mode, timeout):
            call_count["n"] += 1
            if provider.name == "fail":
                raise ConnectionError("simulated failure")
            return "success from ok"

        r._call_openai_compat = mock_call
        r._call_anthropic = mock_call
        r._call_ollama = mock_call
        # Passthrough type isn't dispatched by default, so let's use openai_compatible
        cfg2 = MindosConfig.from_dict({
            "models": [
                {"name": "fail", "type": "openai_compatible", "model": "f",
                 "priority": 1, "for": [], "api_key_env": ""},
                {"name": "ok", "type": "openai_compatible", "model": "o",
                 "priority": 2, "for": [], "api_key_env": ""},
            ],
        })
        # Override availability for testing
        for p in cfg2.providers:
            p.type = "openai_compatible"
            p._test_available = True

        r2 = ModelRouter(cfg2)
        r2._call_openai_compat = mock_call
        # Make providers appear available
        original_available = ModelProvider.available.fget

        with patch.object(ModelProvider, 'available', new_callable=lambda: property(lambda self: True)):
            result = r2.call_llm(system="test", user="test", task="chat")
            assert result == "success from ok"
            assert call_count["n"] == 2  # tried fail, then ok

    def test_all_fail_returns_none(self):
        cfg = MindosConfig.from_dict({
            "models": [
                {"name": "a", "type": "openai_compatible", "model": "a", "priority": 1, "for": []},
            ],
        })
        r = ModelRouter(cfg)
        r._call_openai_compat = lambda *args, **kw: (_ for _ in ()).throw(RuntimeError("down"))

        with patch.object(ModelProvider, 'available', new_callable=lambda: property(lambda self: True)):
            result = r.call_llm(system="s", user="u", task="chat")
            assert result is None

    def test_cache_hit(self):
        cfg = MindosConfig.from_dict({
            "models": [
                {"name": "a", "type": "openai_compatible", "model": "a", "priority": 1, "for": []},
            ],
        })
        r = ModelRouter(cfg)
        call_count = {"n": 0}

        def mock_call(*args, **kw):
            call_count["n"] += 1
            return "cached_result"

        r._call_openai_compat = mock_call

        with patch.object(ModelProvider, 'available', new_callable=lambda: property(lambda self: True)):
            r1 = r.call_llm(system="s", user="u", task="chat", use_cache=True)
            r2 = r.call_llm(system="s", user="u", task="chat", use_cache=True)
            assert r1 == "cached_result"
            assert r2 == "cached_result"
            assert call_count["n"] == 1  # only called once


# ── Config file load ────────────────────────────────────────────────

class TestConfigLoad:
    def test_load_creates_from_env(self):
        """Issue #1: load() should use from_env() when no config.yaml exists."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"}, clear=False):
                cfg = MindosConfig.load(Path(tmp))
                assert (Path(tmp) / "config.yaml").exists()
                names = [p.name for p in cfg.providers]
                assert "openrouter" in names  # from_env detected it

    def test_load_creates_default_no_keys(self):
        """When no API keys are set, load() still creates config with ollama fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            # Clear all API keys
            env_overrides = {k: "" for k in [
                "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY",
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY"
            ]}
            with patch.dict(os.environ, env_overrides, clear=False):
                cfg = MindosConfig.load(Path(tmp))
                assert (Path(tmp) / "config.yaml").exists()
                assert len(cfg.providers) > 0

    def test_load_reads_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                '{"models": [{"name": "custom", "type": "passthrough", "model": "m"}]}',
                encoding="utf-8",
            )
            cfg = MindosConfig.load(Path(tmp))
            names = [p.name for p in cfg.providers]
            assert "custom" in names


class TestWarningOncePerTask:
    """Issue #2: 'No available provider' warning should only fire once per task."""

    def test_warning_fires_once(self):
        import logging
        cfg = MindosConfig.from_dict({
            "models": [{"name": "x", "type": "openai_compatible",
                         "model": "x", "priority": 1,
                         "for": ["chat"], "api_key_env": "NONEXISTENT_XYZ"}],
        })
        router = ModelRouter(cfg)
        with patch.object(ModelProvider, 'available',
                          new_callable=lambda: property(lambda self: False)):
            with patch("mindos.config.log") as mock_log:
                router.call_llm(system="s", user="u", task="commit_digest")
                router.call_llm(system="s", user="u", task="commit_digest")
                router.call_llm(system="s", user="u", task="commit_digest")
                # Should only warn once for the same task
                warn_calls = [c for c in mock_log.warning.call_args_list
                              if "commit_digest" in str(c)]
                assert len(warn_calls) == 1
