"""Tests for core/sizing.py — auto_correct_tier heuristics."""

from __future__ import annotations

from agent_estimate.core.models import SizeTier, SizingResult
from agent_estimate.core.sizing import auto_correct_tier, classify_task


def _sizing(tier: SizeTier) -> SizingResult:
    return classify_task(
        {
            SizeTier.XS: "trivial one-liner rename",
            SizeTier.S: "small simple task",
            SizeTier.M: "medium standard feature",
            SizeTier.L: "large complex multi-file change",
            SizeTier.XL: "massive epic rewrite overhaul",
        }[tier]
    )


# ---------------------------------------------------------------------------
# Upgrade to L — tests threshold
# ---------------------------------------------------------------------------


class TestUpgradeToLViaTests:
    def test_21_tests_upgrades_m_to_l(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=21)
        assert result.sizing.tier == SizeTier.L

    def test_exactly_20_tests_does_not_upgrade(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=20)
        assert result.sizing.tier == SizeTier.M

    def test_44_tests_upgrades_m_to_l(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=44)
        assert result.sizing.tier == SizeTier.L

    def test_upgrade_includes_warning_message(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=44)
        assert len(result.warnings) == 1
        assert "Upgraded M\u2192L" in result.warnings[0]
        assert "44" in result.warnings[0]

    def test_upgrade_from_s_to_l_via_tests(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=30)
        assert result.sizing.tier == SizeTier.L

    def test_already_l_no_change_on_tests(self) -> None:
        sizing = _sizing(SizeTier.L)
        result = auto_correct_tier(sizing, estimated_tests=100)
        assert result.sizing.tier == SizeTier.L
        assert result.warnings == ()

    def test_xl_not_downgraded_by_test_upgrade_check(self) -> None:
        sizing = _sizing(SizeTier.XL)
        result = auto_correct_tier(sizing, estimated_tests=100)
        assert result.sizing.tier == SizeTier.XL
        assert result.warnings == ()


# ---------------------------------------------------------------------------
# Upgrade to L — lines threshold
# ---------------------------------------------------------------------------


class TestUpgradeToLViaLines:
    def test_201_lines_upgrades_m_to_l(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_lines=201)
        assert result.sizing.tier == SizeTier.L

    def test_exactly_200_lines_does_not_upgrade(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_lines=200)
        assert result.sizing.tier == SizeTier.M

    def test_485_lines_upgrades_m_to_l(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_lines=485)
        assert result.sizing.tier == SizeTier.L

    def test_upgrade_lines_warning_content(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_lines=485)
        assert len(result.warnings) == 1
        assert "Upgraded M\u2192L" in result.warnings[0]
        assert "485" in result.warnings[0]


# ---------------------------------------------------------------------------
# Upgrade to L — concerns threshold
# ---------------------------------------------------------------------------


class TestUpgradeToLViaConcerns:
    def test_3_concerns_upgrades_m_to_l(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, num_concerns=3)
        assert result.sizing.tier == SizeTier.L

    def test_2_concerns_does_not_upgrade(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, num_concerns=2)
        assert result.sizing.tier == SizeTier.M

    def test_5_concerns_upgrades_s_to_l(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, num_concerns=5)
        assert result.sizing.tier == SizeTier.L

    def test_upgrade_concerns_warning_content(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, num_concerns=3)
        assert len(result.warnings) == 1
        assert "Upgraded M\u2192L" in result.warnings[0]
        assert "3" in result.warnings[0]


# ---------------------------------------------------------------------------
# Downgrade to XS
# ---------------------------------------------------------------------------


class TestDowngradeToXS:
    def test_small_task_downgrades_s_to_xs(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=2, estimated_lines=20)
        assert result.sizing.tier == SizeTier.XS

    def test_exactly_3_tests_and_29_lines_downgrades(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=3, estimated_lines=29)
        assert result.sizing.tier == SizeTier.XS

    def test_4_tests_does_not_downgrade(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=4, estimated_lines=20)
        assert result.sizing.tier == SizeTier.S

    def test_30_lines_does_not_downgrade(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=2, estimated_lines=30)
        assert result.sizing.tier == SizeTier.S

    def test_already_xs_no_change(self) -> None:
        sizing = _sizing(SizeTier.XS)
        result = auto_correct_tier(sizing, estimated_tests=1, estimated_lines=10)
        assert result.sizing.tier == SizeTier.XS
        assert result.warnings == ()

    def test_downgrade_requires_both_tests_and_lines(self) -> None:
        sizing = _sizing(SizeTier.S)
        # Only tests provided — no downgrade
        result = auto_correct_tier(sizing, estimated_tests=2)
        assert result.sizing.tier == SizeTier.S

    def test_downgrade_warning_content(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=2, estimated_lines=20)
        assert len(result.warnings) == 1
        assert "Downgraded S\u2192XS" in result.warnings[0]

    def test_m_task_downgrades_to_xs(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=1, estimated_lines=10)
        assert result.sizing.tier == SizeTier.XS


# ---------------------------------------------------------------------------
# No change cases
# ---------------------------------------------------------------------------


class TestNoChange:
    def test_no_signals_no_change(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing)
        assert result.sizing.tier == SizeTier.M
        assert result.warnings == ()

    def test_none_signals_all_no_change(self) -> None:
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(
            sizing, estimated_tests=None, estimated_lines=None, num_concerns=None
        )
        assert result.sizing.tier == SizeTier.S
        assert result.warnings == ()

    def test_upgrade_takes_precedence_over_downgrade(self) -> None:
        # High tests should trigger upgrade, not downgrade
        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=25, estimated_lines=20)
        assert result.sizing.tier == SizeTier.L

    def test_corrected_sizing_retains_task_type(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=44)
        assert result.sizing.task_type == sizing.task_type

    def test_corrected_sizing_has_auto_corrected_signal(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=44)
        assert "auto-corrected-to-L" in result.sizing.signals

    def test_no_correction_no_extra_signal(self) -> None:
        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=5)
        assert not any("auto-corrected" in s for s in result.sizing.signals)


# ---------------------------------------------------------------------------
# Baselines updated after correction
# ---------------------------------------------------------------------------


class TestCorrectedBaselines:
    def test_upgraded_to_l_uses_l_baselines(self) -> None:
        from agent_estimate.core.sizing import TIER_BASELINES

        sizing = _sizing(SizeTier.M)
        result = auto_correct_tier(sizing, estimated_tests=44)
        o, m, p = TIER_BASELINES[SizeTier.L]
        assert result.sizing.baseline_optimistic == o
        assert result.sizing.baseline_most_likely == m
        assert result.sizing.baseline_pessimistic == p

    def test_downgraded_to_xs_uses_xs_baselines(self) -> None:
        from agent_estimate.core.sizing import TIER_BASELINES

        sizing = _sizing(SizeTier.S)
        result = auto_correct_tier(sizing, estimated_tests=2, estimated_lines=20)
        o, m, p = TIER_BASELINES[SizeTier.XS]
        assert result.sizing.baseline_optimistic == o
        assert result.sizing.baseline_most_likely == m
        assert result.sizing.baseline_pessimistic == p
