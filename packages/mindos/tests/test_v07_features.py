"""Tests for v0.7 features: Constitution, Damping, Importance Trigger."""

import json
import pytest

from mindos.constitution import Constitution, ConstitutionRule
from mindos.damping import WritebackDamper, DampingConfig
from mindos.importance import ImportanceTrigger, estimate_importance


# ── Constitution ──────────────────────────────────────────────────────


class TestConstitutionRule:
    def test_trait_immutable_prevents_removal(self):
        c = Constitution([
            ConstitutionRule("lock-empathy", "trait_immutable", "empathy"),
        ])
        current = {"traits": ["empathy", "humor"]}
        proposed = {"traits": ["humor"]}  # empathy removed
        result, violations = c.validate_writeback(current, proposed)
        assert "empathy" in result["traits"]
        assert len(violations) == 1
        assert "empathy" in violations[0]

    def test_trait_immutable_allows_keeping(self):
        c = Constitution([
            ConstitutionRule("lock-empathy", "trait_immutable", "empathy"),
        ])
        current = {"traits": ["empathy", "humor"]}
        proposed = {"traits": ["empathy", "humor", "curiosity"]}
        result, violations = c.validate_writeback(current, proposed)
        assert len(violations) == 0

    def test_range_lock_clamps_low(self):
        c = Constitution([
            ConstitutionRule("empathy-floor", "range_lock", "empathy", {"min": 0.5}),
        ])
        current = {"scores": {"empathy": 0.7}}
        proposed = {"scores": {"empathy": 0.3}}
        result, violations = c.validate_writeback(current, proposed)
        assert result["scores"]["empathy"] == 0.5
        assert len(violations) == 1

    def test_range_lock_clamps_high(self):
        c = Constitution([
            ConstitutionRule("ego-cap", "range_lock", "ego", {"max": 0.8}),
        ])
        current = {"scores": {"ego": 0.6}}
        proposed = {"scores": {"ego": 0.95}}
        result, violations = c.validate_writeback(current, proposed)
        assert result["scores"]["ego"] == 0.8

    def test_max_delta_clamps(self):
        c = Constitution([
            ConstitutionRule("slow-change", "max_delta", "*", {"delta": 0.1}),
        ])
        current = {"scores": {"curiosity": 0.5, "humor": 0.3}}
        proposed = {"scores": {"curiosity": 0.8, "humor": 0.3}}  # delta=0.3 > 0.1
        result, violations = c.validate_writeback(current, proposed)
        assert abs(result["scores"]["curiosity"] - 0.6) < 0.01
        assert len(violations) == 1

    def test_value_required(self):
        c = Constitution([
            ConstitutionRule("must-honest", "value_required", "honesty"),
        ])
        current = {"values": ["honesty", "kindness"]}
        proposed = {"values": ["kindness"]}  # honesty removed
        result, violations = c.validate_writeback(current, proposed)
        assert "honesty" in result["values"]
        assert len(violations) == 1

    def test_from_anchors_backward_compat(self):
        c = Constitution.from_anchors(["honest", "kind"])
        assert len(c.rules) == 2
        assert c.is_locked("honest")
        assert c.is_locked("kind")
        assert not c.is_locked("funny")

    def test_to_dict_roundtrip(self):
        c = Constitution([
            ConstitutionRule("r1", "trait_immutable", "empathy"),
            ConstitutionRule("r2", "range_lock", "ego", {"max": 0.8}),
        ])
        data = c.to_dict()
        c2 = Constitution.from_dict(data)
        assert len(c2.rules) == 2
        assert c2.rules[0].id == "r1"

    def test_empty_constitution_passes_everything(self):
        c = Constitution()
        current = {"traits": ["a"], "scores": {"x": 0.5}}
        proposed = {"traits": ["b"], "scores": {"x": 0.9}}
        result, violations = c.validate_writeback(current, proposed)
        assert len(violations) == 0

    def test_multiple_rules_compose(self):
        c = Constitution([
            ConstitutionRule("lock-empathy", "trait_immutable", "empathy"),
            ConstitutionRule("empathy-floor", "range_lock", "empathy", {"min": 0.5}),
            ConstitutionRule("slow", "max_delta", "*", {"delta": 0.1}),
        ])
        current = {"traits": ["empathy"], "scores": {"empathy": 0.7}}
        proposed = {"traits": [], "scores": {"empathy": 0.2}}
        result, violations = c.validate_writeback(current, proposed)
        assert "empathy" in result["traits"]
        assert result["scores"]["empathy"] >= 0.5
        assert len(violations) >= 2


# ── Writeback Damping ─────────────────────────────────────────────────


class TestDamping:
    def test_no_history_returns_proposed(self):
        d = WritebackDamper()
        assert d.apply("curiosity", [], 0.7) == 0.7

    def test_max_delta_clamping(self):
        d = WritebackDamper(DampingConfig(max_delta=0.1))
        # Proposed: 0.5 → 0.8 (delta=0.3, > 0.1)
        result = d.apply("curiosity", [0.5], 0.8)
        assert abs(result - 0.6) < 0.01

    def test_max_delta_negative(self):
        d = WritebackDamper(DampingConfig(max_delta=0.1))
        result = d.apply("curiosity", [0.5], 0.1)  # delta=-0.4
        assert abs(result - 0.4) < 0.01

    def test_small_delta_not_clamped(self):
        d = WritebackDamper(DampingConfig(max_delta=0.15))
        result = d.apply("curiosity", [0.5], 0.6)  # delta=0.1 < 0.15
        assert abs(result - 0.6) < 0.01

    def test_oscillation_detection(self):
        d = WritebackDamper(DampingConfig(
            max_delta=0.5,  # high so delta clamping doesn't interfere
            oscillation_window=5,
            oscillation_threshold=3,
            damping_factor=0.5,
        ))
        # Oscillating history: up, down, up, down, up
        history = [0.5, 0.6, 0.5, 0.6, 0.5]
        result = d.apply("curiosity", history, 0.7)
        # delta=0.2, oscillation detected → delta * 0.5 = 0.1
        assert abs(result - 0.6) < 0.01

    def test_no_oscillation_normal_step(self):
        d = WritebackDamper(DampingConfig(
            max_delta=0.5,
            oscillation_threshold=3,
        ))
        # Monotonically increasing — no oscillation
        history = [0.3, 0.4, 0.5, 0.6, 0.7]
        result = d.apply("curiosity", history, 0.9)
        assert abs(result - 0.9) < 0.01

    def test_apply_dict(self):
        d = WritebackDamper(DampingConfig(max_delta=0.1))
        current = {"a": 0.5, "b": 0.3}
        proposed = {"a": 0.8, "b": 0.35}
        history = {"a": [0.5], "b": [0.3]}
        result = d.apply_dict(current, proposed, history)
        assert abs(result["a"] - 0.6) < 0.01  # clamped
        assert abs(result["b"] - 0.35) < 0.01  # not clamped

    def test_count_reversals(self):
        d = WritebackDamper()
        assert d._count_reversals([0.5, 0.6, 0.5, 0.6, 0.5]) == 3
        assert d._count_reversals([0.5, 0.6, 0.7]) == 0
        assert d._count_reversals([0.5]) == 0
        assert d._count_reversals([]) == 0


# ── Importance Trigger ────────────────────────────────────────────────


class TestImportanceTrigger:
    def test_accumulate_below_threshold(self):
        t = ImportanceTrigger(threshold=100.0)
        assert t.accumulate(5.0) is False
        assert t.current == 5.0

    def test_accumulate_crosses_threshold(self):
        t = ImportanceTrigger(threshold=10.0)
        assert t.accumulate(5.0) is False
        assert t.accumulate(6.0) is True

    def test_reset(self):
        t = ImportanceTrigger(threshold=100.0)
        t.accumulate(50.0)
        t.reset()
        assert t.current == 0.0

    def test_progress(self):
        t = ImportanceTrigger(threshold=100.0)
        t.accumulate(25.0)
        assert abs(t.progress - 0.25) < 0.01

    def test_progress_capped_at_one(self):
        t = ImportanceTrigger(threshold=10.0)
        t.accumulate(20.0)
        assert t.progress == 1.0

    def test_zero_threshold(self):
        t = ImportanceTrigger(threshold=0.0)
        assert t.progress == 0.0


class TestEstimateImportance:
    def test_empty(self):
        assert estimate_importance([], "") == 0.0

    def test_single_fact(self):
        score = estimate_importance([{"type": "fact", "confidence": 0.8}])
        assert score == round(0.8 * 1.5, 2)

    def test_relation_high_weight(self):
        score = estimate_importance([{"type": "relation", "confidence": 1.0}])
        assert score == 3.0

    def test_episode_bonus(self):
        score = estimate_importance([], "some episode summary")
        assert score == 2.0

    def test_mixed(self):
        facts = [
            {"type": "fact", "confidence": 0.8},
            {"type": "preference", "confidence": 0.9},
        ]
        score = estimate_importance(facts, "episode")
        expected = round(0.8 * 1.5 + 0.9 * 2.0 + 2.0, 2)
        assert score == expected

    def test_default_confidence(self):
        score = estimate_importance([{"type": "skill"}])
        # default confidence 0.7, skill weight 2.5
        assert score == round(0.7 * 2.5, 2)


# ── Integration: L4 wiring ───────────────────────────────────────────


class TestL4Integration:
    """Test that L4 Self correctly uses the new v0.7 modules."""

    def test_l4_has_constitution(self):
        from mindos.layers.l4_self import Self
        from mindos.store import MemoryStore
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "test.db"))
            identity = {"name": "test", "traits": ["kind"], "anchors": ["kind"]}
            l4 = Self(store, identity)
            assert l4.constitution is not None
            assert l4.constitution.is_locked("kind")

    def test_l4_has_damper(self):
        from mindos.layers.l4_self import Self
        from mindos.store import MemoryStore
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "test.db"))
            l4 = Self(store, {"name": "test", "traits": []})
            assert l4.damper is not None

    def test_l4_has_importance_trigger(self):
        from mindos.layers.l4_self import Self
        from mindos.store import MemoryStore
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "test.db"))
            l4 = Self(store, {"name": "test", "traits": []})
            assert l4.importance_trigger is not None
            assert l4.importance_trigger.current == 0.0
