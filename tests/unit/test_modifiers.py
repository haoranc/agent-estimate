"""Dedicated tests for core/modifiers.py covering boundary values and composition."""

from __future__ import annotations

import pytest

from agent_estimate.core.models import ReviewMode
from agent_estimate.core.modifiers import (
    apply_modifiers,
    build_modifier_set,
    compute_review_overhead,
)


# ---------------------------------------------------------------------------
# Boundary values for spec_clarity
# ---------------------------------------------------------------------------


class TestSpecClarityBoundaries:
    def test_spec_clarity_lower_boundary_accepted(self) -> None:
        mods = build_modifier_set(spec_clarity=0.8)
        assert mods.spec_clarity == pytest.approx(0.8)

    def test_spec_clarity_upper_boundary_accepted(self) -> None:
        mods = build_modifier_set(spec_clarity=1.3)
        assert mods.spec_clarity == pytest.approx(1.3)

    def test_spec_clarity_below_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="spec_clarity"):
            build_modifier_set(spec_clarity=0.79)

    def test_spec_clarity_above_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="spec_clarity"):
            build_modifier_set(spec_clarity=1.31)


# ---------------------------------------------------------------------------
# Boundary values for warm_context
# ---------------------------------------------------------------------------


class TestWarmContextBoundaries:
    def test_warm_context_lower_boundary_accepted(self) -> None:
        mods = build_modifier_set(warm_context=0.85)
        assert mods.warm_context == pytest.approx(0.85)

    def test_warm_context_upper_boundary_accepted(self) -> None:
        mods = build_modifier_set(warm_context=1.15)
        assert mods.warm_context == pytest.approx(1.15)

    def test_warm_context_below_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="warm_context"):
            build_modifier_set(warm_context=0.84)

    def test_warm_context_above_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="warm_context"):
            build_modifier_set(warm_context=1.16)


# ---------------------------------------------------------------------------
# Boundary values for agent_fit
# ---------------------------------------------------------------------------


class TestAgentFitBoundaries:
    def test_agent_fit_lower_boundary_accepted(self) -> None:
        mods = build_modifier_set(agent_fit=0.9)
        assert mods.agent_fit == pytest.approx(0.9)

    def test_agent_fit_upper_boundary_accepted(self) -> None:
        mods = build_modifier_set(agent_fit=1.2)
        assert mods.agent_fit == pytest.approx(1.2)

    def test_agent_fit_below_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="agent_fit"):
            build_modifier_set(agent_fit=0.89)

    def test_agent_fit_above_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="agent_fit"):
            build_modifier_set(agent_fit=1.21)


# ---------------------------------------------------------------------------
# Combined modifier product correctness
# ---------------------------------------------------------------------------


class TestCombinedModifierProduct:
    def test_combined_is_exact_product_of_three(self) -> None:
        sc, wc, af = 1.2, 1.05, 1.1
        mods = build_modifier_set(spec_clarity=sc, warm_context=wc, agent_fit=af)
        assert mods.combined == pytest.approx(sc * wc * af)

    def test_all_lower_boundaries_product(self) -> None:
        mods = build_modifier_set(spec_clarity=0.8, warm_context=0.85, agent_fit=0.9)
        assert mods.combined == pytest.approx(0.8 * 0.85 * 0.9)

    def test_all_upper_boundaries_product(self) -> None:
        mods = build_modifier_set(spec_clarity=1.3, warm_context=1.15, agent_fit=1.2)
        assert mods.combined == pytest.approx(1.3 * 1.15 * 1.2)

    def test_combined_stored_correctly_in_frozen_dataclass(self) -> None:
        mods = build_modifier_set(spec_clarity=1.1, warm_context=1.0, agent_fit=1.0)
        assert mods.combined == pytest.approx(1.1)
        with pytest.raises(AttributeError):
            mods.combined = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# apply_modifiers
# ---------------------------------------------------------------------------


class TestApplyModifiers:
    def test_neutral_modifier_leaves_base_unchanged(self) -> None:
        mods = build_modifier_set()
        assert apply_modifiers(100.0, mods) == pytest.approx(100.0)

    def test_scale_up(self) -> None:
        mods = build_modifier_set(spec_clarity=1.3)
        assert apply_modifiers(100.0, mods) == pytest.approx(130.0)

    def test_scale_down(self) -> None:
        mods = build_modifier_set(spec_clarity=0.8, warm_context=0.85, agent_fit=0.9)
        expected = 200.0 * 0.8 * 0.85 * 0.9
        assert apply_modifiers(200.0, mods) == pytest.approx(expected)

    def test_zero_base_gives_zero(self) -> None:
        mods = build_modifier_set(spec_clarity=1.2)
        assert apply_modifiers(0.0, mods) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_review_overhead — all ReviewMode values
# ---------------------------------------------------------------------------


class TestComputeReviewOverhead:
    def test_none_mode_is_zero(self) -> None:
        assert compute_review_overhead(ReviewMode.NONE) == pytest.approx(0.0)

    def test_self_mode_is_seven_and_half(self) -> None:
        assert compute_review_overhead(ReviewMode.SELF) == pytest.approx(7.5)

    def test_two_lgtm_mode_is_seventeen_and_half(self) -> None:
        assert compute_review_overhead(ReviewMode.TWO_LGTM) == pytest.approx(17.5)

    def test_all_review_modes_covered(self) -> None:
        for mode in ReviewMode:
            overhead = compute_review_overhead(mode)
            assert overhead >= 0.0
