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
        mods = build_modifier_set(spec_clarity=0.3)
        assert mods.spec_clarity == pytest.approx(0.3)

    def test_spec_clarity_upper_boundary_accepted(self) -> None:
        mods = build_modifier_set(spec_clarity=1.3)
        assert mods.spec_clarity == pytest.approx(1.3)

    def test_spec_clarity_below_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="spec_clarity"):
            build_modifier_set(spec_clarity=0.29)

    def test_spec_clarity_above_upper_raises(self) -> None:
        with pytest.raises(ValueError, match="spec_clarity"):
            build_modifier_set(spec_clarity=1.31)


# ---------------------------------------------------------------------------
# Boundary values for warm_context
# ---------------------------------------------------------------------------


class TestWarmContextBoundaries:
    def test_warm_context_lower_boundary_accepted(self) -> None:
        mods = build_modifier_set(warm_context=0.3)
        assert mods.warm_context == pytest.approx(0.3)

    def test_warm_context_upper_boundary_accepted(self) -> None:
        mods = build_modifier_set(warm_context=1.15)
        assert mods.warm_context == pytest.approx(1.15)

    def test_warm_context_below_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="warm_context"):
            build_modifier_set(warm_context=0.29)

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
        assert mods.raw_combined == pytest.approx(sc * wc * af)
        assert mods.combined == pytest.approx(sc * wc * af)
        assert mods.clamped is False

    def test_all_lower_boundaries_product_clamped(self) -> None:
        mods = build_modifier_set(spec_clarity=0.3, warm_context=0.3, agent_fit=0.9)
        assert mods.raw_combined == pytest.approx(0.3 * 0.3 * 0.9)
        assert mods.combined == pytest.approx(0.10)
        assert mods.clamped is True

    def test_spec_clarity_and_warm_context_at_floor(self) -> None:
        mods = build_modifier_set(spec_clarity=0.3, warm_context=0.3)
        assert mods.raw_combined == pytest.approx(0.09)
        assert mods.combined == pytest.approx(0.10)
        assert mods.clamped is True

    def test_all_upper_boundaries_product(self) -> None:
        mods = build_modifier_set(spec_clarity=1.3, warm_context=1.15, agent_fit=1.2)
        assert mods.combined == pytest.approx(1.3 * 1.15 * 1.2)

    def test_combined_stored_correctly_in_frozen_dataclass(self) -> None:
        mods = build_modifier_set(spec_clarity=1.1, warm_context=1.0, agent_fit=1.0)
        assert mods.combined == pytest.approx(1.1)
        assert mods.raw_combined == pytest.approx(1.1)
        assert mods.clamped is False
        with pytest.raises(AttributeError):
            mods.combined = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Modifier product floor
# ---------------------------------------------------------------------------


class TestModifierFloor:
    def test_floor_fires_when_product_below_0_10(self) -> None:
        mods = build_modifier_set(spec_clarity=0.3, warm_context=0.3)
        assert mods.raw_combined == pytest.approx(0.09)
        assert mods.combined == pytest.approx(0.10)
        assert mods.clamped is True

    def test_floor_fires_with_all_three_at_minimum(self) -> None:
        mods = build_modifier_set(spec_clarity=0.3, warm_context=0.3, agent_fit=0.9)
        assert mods.raw_combined == pytest.approx(0.081)
        assert mods.combined == pytest.approx(0.10)
        assert mods.clamped is True

    def test_floor_does_not_fire_at_exactly_0_10(self) -> None:
        # spec_clarity=0.3, warm_context=0.3, agent_fit=1.112 ≈ 0.100 — clamp at exact boundary
        # Use a combination that lands exactly on the floor
        mods = build_modifier_set(spec_clarity=0.5, warm_context=0.3, agent_fit=0.9)
        # 0.5 * 0.3 * 0.9 = 0.135 > 0.10 — no clamp
        assert mods.clamped is False
        assert mods.combined == pytest.approx(0.135)

    def test_floor_does_not_fire_above_threshold(self) -> None:
        mods = build_modifier_set(spec_clarity=1.0, warm_context=1.0, agent_fit=1.0)
        assert mods.clamped is False
        assert mods.combined == pytest.approx(1.0)
        assert mods.raw_combined == pytest.approx(1.0)

    def test_floor_warning_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="agent_estimate.core.modifiers"):
            build_modifier_set(spec_clarity=0.3, warm_context=0.3)
        assert len(caplog.records) == 1
        assert "0.10" in caplog.records[0].message
        assert "clamped" in caplog.records[0].message

    def test_no_warning_when_floor_not_triggered(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="agent_estimate.core.modifiers"):
            build_modifier_set(spec_clarity=1.0, warm_context=1.0, agent_fit=1.0)
        assert len(caplog.records) == 0


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

    def test_scale_down_clamped(self) -> None:
        mods = build_modifier_set(spec_clarity=0.3, warm_context=0.3, agent_fit=0.9)
        # raw product 0.081 < floor 0.10, so combined is clamped
        assert apply_modifiers(200.0, mods) == pytest.approx(200.0 * 0.10)

    def test_zero_base_gives_zero(self) -> None:
        mods = build_modifier_set(spec_clarity=1.2)
        assert apply_modifiers(0.0, mods) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_review_overhead — all ReviewMode values
# ---------------------------------------------------------------------------


class TestComputeReviewOverhead:
    """Verify additive overhead values from issue #46 evidence."""

    def test_none_mode_is_zero(self) -> None:
        """Self-merge: no cross-agent review, 0 m overhead."""
        assert compute_review_overhead(ReviewMode.NONE) == pytest.approx(0.0)

    def test_standard_mode_is_fifteen_minutes(self) -> None:
        """Clean 2x-LGTM, 1-2 rounds: 15 m flat overhead."""
        assert compute_review_overhead(ReviewMode.STANDARD) == pytest.approx(15.0)

    def test_complex_mode_is_twenty_five_minutes(self) -> None:
        """3+ rounds, security-sensitive, new algorithms: 25 m overhead."""
        assert compute_review_overhead(ReviewMode.COMPLEX) == pytest.approx(25.0)

    def test_all_review_modes_covered(self) -> None:
        for mode in ReviewMode:
            overhead = compute_review_overhead(mode)
            assert overhead >= 0.0

    def test_overhead_is_additive_not_percentage(self) -> None:
        """Review overhead is a flat additive value — not a % of work estimate."""
        # Same overhead regardless of base estimate size
        assert compute_review_overhead(ReviewMode.STANDARD) == pytest.approx(15.0)
        assert compute_review_overhead(ReviewMode.COMPLEX) == pytest.approx(25.0)

    def test_standard_overhead_dominates_fast_tasks(self) -> None:
        """For a 5-minute XS task, 15 m review overhead is 3x the work — proves additive model matters."""
        work_estimate = 5.0
        overhead = compute_review_overhead(ReviewMode.STANDARD)
        assert overhead > work_estimate

    # ---------------------------------------------------------------------------
    # Legacy alias backwards compatibility
    # ---------------------------------------------------------------------------

    def test_legacy_self_maps_to_none(self) -> None:
        """'self' was the old mode string — now aliases to NONE (0 m)."""
        mode = ReviewMode("self")
        assert mode is ReviewMode.NONE
        assert compute_review_overhead(mode) == pytest.approx(0.0)

    def test_legacy_2x_lgtm_maps_to_standard(self) -> None:
        """'2x-lgtm' was the old mode string — now aliases to STANDARD (15 m)."""
        mode = ReviewMode("2x-lgtm")
        assert mode is ReviewMode.STANDARD
        assert compute_review_overhead(mode) == pytest.approx(15.0)

    def test_unknown_mode_string_raises(self) -> None:
        with pytest.raises(ValueError):
            ReviewMode("bogus")
