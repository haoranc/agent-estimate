"""Tests for Pydantic config models and dataclass constraints in core/models.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_estimate.core.models import (
    AgentProfile,
    EstimationConfig,
    ProjectSettings,
    SizeTier,
    SizingResult,
    TaskType,
)
from agent_estimate.core.modifiers import build_modifier_set
from agent_estimate.core.sizing import TIER_BASELINES


# ---------------------------------------------------------------------------
# AgentProfile validation
# ---------------------------------------------------------------------------


class TestAgentProfileValidation:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "name": "Claude",
            "capabilities": ["code"],
            "parallelism": 1,
            "cost_per_turn": 0.0,
            "model_tier": "frontier",
        }
        base.update(overrides)
        return base

    def test_valid_profile_parses(self) -> None:
        profile = AgentProfile(**self._valid())
        assert profile.name == "Claude"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            AgentProfile(**self._valid(name=""))

    def test_whitespace_only_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            AgentProfile(**self._valid(name="   "))

    def test_zero_parallelism_raises(self) -> None:
        with pytest.raises(ValidationError, match="parallelism"):
            AgentProfile(**self._valid(parallelism=0))

    def test_negative_parallelism_raises(self) -> None:
        with pytest.raises(ValidationError, match="parallelism"):
            AgentProfile(**self._valid(parallelism=-1))

    def test_negative_cost_per_turn_raises(self) -> None:
        with pytest.raises(ValidationError, match="cost_per_turn"):
            AgentProfile(**self._valid(cost_per_turn=-0.01))

    def test_zero_cost_per_turn_accepted(self) -> None:
        profile = AgentProfile(**self._valid(cost_per_turn=0.0))
        assert profile.cost_per_turn == 0.0

    def test_empty_capabilities_list_raises(self) -> None:
        with pytest.raises(ValidationError, match="capabilities"):
            AgentProfile(**self._valid(capabilities=[]))

    def test_extra_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            AgentProfile(**self._valid(unknown_field="oops"))


# ---------------------------------------------------------------------------
# ProjectSettings validation
# ---------------------------------------------------------------------------


class TestProjectSettingsValidation:
    def _valid(self, **overrides: object) -> dict:
        base: dict = {
            "friction_multiplier": 1.0,
            "inter_wave_overhead": 0.0,
            "review_overhead": 0.0,
            "metr_fallback_threshold": 40.0,
        }
        base.update(overrides)
        return base

    def test_valid_settings_parse(self) -> None:
        s = ProjectSettings(**self._valid())
        assert s.friction_multiplier == pytest.approx(1.0)

    def test_zero_friction_multiplier_raises(self) -> None:
        with pytest.raises(ValidationError, match="friction_multiplier"):
            ProjectSettings(**self._valid(friction_multiplier=0.0))

    def test_negative_friction_multiplier_raises(self) -> None:
        with pytest.raises(ValidationError, match="friction_multiplier"):
            ProjectSettings(**self._valid(friction_multiplier=-1.0))

    def test_negative_review_overhead_raises(self) -> None:
        with pytest.raises(ValidationError, match="review_overhead"):
            ProjectSettings(**self._valid(review_overhead=-0.1))

    def test_negative_inter_wave_overhead_raises(self) -> None:
        with pytest.raises(ValidationError, match="inter_wave_overhead"):
            ProjectSettings(**self._valid(inter_wave_overhead=-0.5))

    def test_zero_metr_fallback_threshold_raises(self) -> None:
        with pytest.raises(ValidationError, match="metr_fallback_threshold"):
            ProjectSettings(**self._valid(metr_fallback_threshold=0.0))


# ---------------------------------------------------------------------------
# EstimationConfig
# ---------------------------------------------------------------------------


class TestEstimationConfig:
    def _agent(self) -> AgentProfile:
        return AgentProfile(
            name="Claude",
            capabilities=["code"],
            parallelism=1,
            cost_per_turn=0.0,
            model_tier="frontier",
        )

    def _settings(self) -> ProjectSettings:
        return ProjectSettings(
            friction_multiplier=1.0,
            inter_wave_overhead=0.0,
            review_overhead=0.0,
            metr_fallback_threshold=40.0,
        )

    def test_valid_config(self) -> None:
        cfg = EstimationConfig(agents=[self._agent()], settings=self._settings())
        assert len(cfg.agents) == 1

    def test_empty_agents_list_raises(self) -> None:
        with pytest.raises(ValidationError, match="agents"):
            EstimationConfig(agents=[], settings=self._settings())

    def test_multiple_agents_accepted(self) -> None:
        cfg = EstimationConfig(
            agents=[self._agent(), self._agent()],
            settings=self._settings(),
        )
        assert len(cfg.agents) == 2


# ---------------------------------------------------------------------------
# SizeTier enum ordering
# ---------------------------------------------------------------------------


class TestSizeTierOrdering:
    def test_all_five_tiers_exist(self) -> None:
        tiers = list(SizeTier)
        assert len(tiers) == 5

    def test_tier_values(self) -> None:
        assert SizeTier.XS.value == "XS"
        assert SizeTier.S.value == "S"
        assert SizeTier.M.value == "M"
        assert SizeTier.L.value == "L"
        assert SizeTier.XL.value == "XL"

    def test_baselines_present_for_all_tiers(self) -> None:
        for tier in SizeTier:
            assert tier in TIER_BASELINES
            o, m, p = TIER_BASELINES[tier]
            assert o < m < p


# ---------------------------------------------------------------------------
# Frozen dataclasses — immutability
# ---------------------------------------------------------------------------


class TestFrozenDataclasses:
    def test_modifier_set_is_frozen(self) -> None:
        mods = build_modifier_set()
        with pytest.raises(AttributeError):
            mods.combined = 99.0  # type: ignore[misc]

    def test_pert_result_is_frozen(self) -> None:
        from agent_estimate.core.pert import compute_pert

        result = compute_pert(10.0, 20.0, 30.0)
        with pytest.raises(AttributeError):
            result.expected = 0.0  # type: ignore[misc]

    def test_sizing_result_is_frozen(self) -> None:
        o, m, p = TIER_BASELINES[SizeTier.S]
        sizing = SizingResult(
            tier=SizeTier.S,
            baseline_optimistic=o,
            baseline_most_likely=m,
            baseline_pessimistic=p,
            task_type=TaskType.FEATURE,
        )
        with pytest.raises(AttributeError):
            sizing.tier = SizeTier.XL  # type: ignore[misc]
