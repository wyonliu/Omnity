"""Tests for Ome v0.7 features: Growth Stages, Maturity Score."""

import pytest

from ome.life.stages import GrowthGate, Capability
from ome.life.maturity import MaturityScorer, MaturitySnapshot, _label_for


# ── Growth Stages ─────────────────────────────────────────────────────


class TestCapability:
    def test_all_capabilities_exist(self):
        assert len(Capability) >= 10

    def test_enum_names(self):
        names = {c.name for c in Capability}
        assert "CHAT" in names
        assert "SOCIAL" in names
        assert "EVOLVE" in names


class TestGrowthGate:
    def test_phase_0_has_basic_capabilities(self):
        g = GrowthGate(phase_id=0)
        assert g.is_unlocked(Capability.CHAT)
        assert g.is_unlocked(Capability.RECALL)
        assert g.is_unlocked(Capability.REMEMBER)
        assert not g.is_unlocked(Capability.SOCIAL)

    def test_phase_1_adds_write_research(self):
        g = GrowthGate(phase_id=1)
        assert g.is_unlocked(Capability.CHAT)  # from phase 0
        assert g.is_unlocked(Capability.WRITE)
        assert g.is_unlocked(Capability.RESEARCH)
        assert g.is_unlocked(Capability.FOLLOW_UPS)
        assert not g.is_unlocked(Capability.SCHEDULE)

    def test_phase_2_adds_schedule_evolve(self):
        g = GrowthGate(phase_id=2)
        assert g.is_unlocked(Capability.SCHEDULE)
        assert g.is_unlocked(Capability.EVOLVE)
        assert g.is_unlocked(Capability.SOUL_CARD)
        assert not g.is_unlocked(Capability.SOCIAL)

    def test_phase_3_unlocks_everything(self):
        g = GrowthGate(phase_id=3)
        assert g.is_unlocked(Capability.SOCIAL)
        assert g.is_unlocked(Capability.SPATIAL)
        assert len(g.locked_capabilities()) == 0

    def test_update_phase(self):
        g = GrowthGate(phase_id=0)
        assert not g.is_unlocked(Capability.WRITE)
        g.update_phase(1)
        assert g.is_unlocked(Capability.WRITE)

    def test_next_unlock(self):
        g = GrowthGate(phase_id=1)
        n = g.next_unlock()
        assert n is not None
        assert n["stage"] == 2
        assert "schedule" in n["capabilities"]

    def test_next_unlock_at_max(self):
        g = GrowthGate(phase_id=3)
        assert g.next_unlock() is None

    def test_to_dict(self):
        g = GrowthGate(phase_id=1)
        d = g.to_dict()
        assert d["phase_id"] == 1
        assert "chat" in d["unlocked"]
        assert "write" in d["unlocked"]
        assert "social" in d["locked"]

    def test_locked_capabilities_shrink_with_phase(self):
        g0 = GrowthGate(phase_id=0)
        g3 = GrowthGate(phase_id=3)
        assert len(g0.locked_capabilities()) > len(g3.locked_capabilities())
        assert len(g3.locked_capabilities()) == 0


# ── Maturity Score ────────────────────────────────────────────────────


class TestMaturityScorer:
    def setup_method(self):
        self.scorer = MaturityScorer()

    def test_zero_state(self):
        snap = self.scorer.score(
            reflection_count=0, trait_count=0,
            memory_total=0, memory_by_type={},
            streak_days=0, skill_competences=[],
            total_interactions=0,
        )
        assert snap.score == 0.0
        assert snap.label == "萌芽"

    def test_moderate_maturity(self):
        snap = self.scorer.score(
            reflection_count=10, trait_count=5,
            memory_total=100, memory_by_type={"fact": 40, "episode": 30, "preference": 20, "relation": 10},
            streak_days=14, skill_competences=[0.3, 0.4, 0.5],
            total_interactions=100,
        )
        assert 0.2 < snap.score < 0.8
        assert snap.reflection_depth > 0
        assert snap.memory_complexity > 0
        assert snap.behavioral_consistency > 0

    def test_high_maturity(self):
        snap = self.scorer.score(
            reflection_count=50, trait_count=15,
            memory_total=1000, memory_by_type={"fact": 300, "episode": 250, "preference": 200, "relation": 150, "skill": 100},
            streak_days=90, skill_competences=[0.8, 0.7, 0.9, 0.6, 0.8],
            total_interactions=500,
        )
        assert snap.score > 0.7
        assert snap.label in ("成熟", "圆满")

    def test_score_capped_at_one(self):
        snap = self.scorer.score(
            reflection_count=1000, trait_count=100,
            memory_total=100000, memory_by_type={"fact": 50000, "episode": 50000},
            streak_days=1000, skill_competences=[1.0] * 20,
            total_interactions=10000,
        )
        assert snap.score <= 1.0

    def test_to_dict(self):
        snap = self.scorer.score(
            reflection_count=5, trait_count=3,
            memory_total=50, memory_by_type={"fact": 30, "episode": 20},
            streak_days=7, skill_competences=[0.3],
            total_interactions=50,
        )
        d = snap.to_dict()
        assert "score" in d
        assert "label" in d
        assert "reflection_depth" in d
        assert "memory_complexity" in d
        assert "behavioral_consistency" in d

    def test_single_type_low_entropy(self):
        snap = self.scorer.score(
            reflection_count=5, trait_count=3,
            memory_total=100, memory_by_type={"fact": 100},
            streak_days=7, skill_competences=[0.3],
            total_interactions=50,
        )
        # Single type = 0 entropy → lower complexity
        snap2 = self.scorer.score(
            reflection_count=5, trait_count=3,
            memory_total=100, memory_by_type={"fact": 25, "episode": 25, "preference": 25, "relation": 25},
            streak_days=7, skill_competences=[0.3],
            total_interactions=50,
        )
        assert snap2.memory_complexity > snap.memory_complexity


class TestLabels:
    def test_label_for_zero(self):
        assert _label_for(0.0) == "萌芽"

    def test_label_for_mid(self):
        assert _label_for(0.5) == "成长"

    def test_label_for_high(self):
        assert _label_for(0.85) == "圆满"

    def test_label_boundaries(self):
        assert _label_for(0.19) == "萌芽"
        assert _label_for(0.2) == "觉醒"
        assert _label_for(0.4) == "成长"
        assert _label_for(0.6) == "成熟"
        assert _label_for(0.8) == "圆满"
