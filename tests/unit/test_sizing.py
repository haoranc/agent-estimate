"""Tests for core/sizing.py — task type detection, edge cases, tier clamping."""

from __future__ import annotations

from agent_estimate.core.models import SizeTier, TaskType
from agent_estimate.core.sizing import _bump_tier, classify_task


# ---------------------------------------------------------------------------
# Task type detection — all types
# ---------------------------------------------------------------------------


class TestTaskTypeDetection:
    def test_boilerplate_detection(self) -> None:
        result = classify_task("Generate boilerplate for the new module")
        assert result.task_type == TaskType.BOILERPLATE

    def test_bug_fix_detection(self) -> None:
        result = classify_task("Fix a regression in the login flow")
        assert result.task_type == TaskType.BUG_FIX

    def test_feature_detection(self) -> None:
        result = classify_task("Implement a new caching layer")
        assert result.task_type == TaskType.FEATURE

    def test_refactor_detection(self) -> None:
        result = classify_task("Refactor the payment module to reduce duplication")
        assert result.task_type == TaskType.REFACTOR

    def test_test_detection(self) -> None:
        result = classify_task("Write test coverage for the auth module")
        assert result.task_type == TaskType.TEST

    def test_docs_detection(self) -> None:
        result = classify_task("Update the README with setup instructions")
        assert result.task_type == TaskType.DOCS

    def test_unknown_type_when_no_keyword(self) -> None:
        result = classify_task("Do the thing with the stuff")
        assert result.task_type == TaskType.UNKNOWN


# ---------------------------------------------------------------------------
# Whitespace-only description
# ---------------------------------------------------------------------------


class TestWhitespaceDescription:
    def test_whitespace_only_defaults_to_m(self) -> None:
        result = classify_task("   ")
        assert result.tier == SizeTier.M
        assert result.task_type == TaskType.UNKNOWN

    def test_whitespace_only_signal_is_no_description_default(self) -> None:
        result = classify_task("\t\n  ")
        assert "no-description-default-M" in result.signals


# ---------------------------------------------------------------------------
# Multiple complexity signals — bump by 2
# ---------------------------------------------------------------------------


class TestComplexitySignalBumps:
    def test_two_complexity_signals_bump_tier_by_one(self) -> None:
        # "simple" → S, plus database + security = 2 complexity signals → S+1 = M
        result = classify_task("Simple database migration with security tokens")
        assert result.tier == SizeTier.M

    def test_four_complexity_signals_bump_tier_by_two(self) -> None:
        # "simple" → S, plus database + security + api + test = 4 signals → S+2 = L
        result = classify_task(
            "Simple database migration with security auth api endpoint and test coverage"
        )
        assert result.tier == SizeTier.L

    def test_one_complexity_signal_no_bump(self) -> None:
        # "simple" → S, plus database = 1 signal → still S
        result = classify_task("Simple database change")
        assert result.tier == SizeTier.S

    def test_complexity_signals_recorded(self) -> None:
        result = classify_task("Simple database migration with security tokens")
        assert "database-change" in result.signals
        assert "security-concern" in result.signals


# ---------------------------------------------------------------------------
# Tier vote median with conflicting signals
# ---------------------------------------------------------------------------


class TestTierVoteMedian:
    def test_conflicting_signals_picks_median(self) -> None:
        # "simple" → S vote, "large" → L vote → median of [S, L] = L (index 1 of 2)
        result = classify_task("Simple but large refactoring task")
        # Sorted: [S, L], median index = 2//2 = 1 → L
        # But "refactoring" triggers structural-change complexity signal → may bump further
        # The structural-change is 1 complexity signal → no bump yet
        assert result.tier in (SizeTier.L, SizeTier.XL)

    def test_all_same_tier_votes_return_that_tier(self) -> None:
        result = classify_task("trivial rename one-liner typo")
        assert result.tier == SizeTier.XS


# ---------------------------------------------------------------------------
# _bump_tier clamping at XL
# ---------------------------------------------------------------------------


class TestBumpTierClamping:
    def test_bump_from_xl_stays_at_xl(self) -> None:
        assert _bump_tier(SizeTier.XL, 1) == SizeTier.XL

    def test_bump_large_steps_from_xl_stays_at_xl(self) -> None:
        assert _bump_tier(SizeTier.XL, 5) == SizeTier.XL

    def test_bump_l_by_one_gives_xl(self) -> None:
        assert _bump_tier(SizeTier.L, 1) == SizeTier.XL

    def test_bump_xs_by_two_gives_m(self) -> None:
        assert _bump_tier(SizeTier.XS, 2) == SizeTier.M

    def test_bump_xs_by_zero_gives_xs(self) -> None:
        assert _bump_tier(SizeTier.XS, 0) == SizeTier.XS

    def test_bump_m_by_ten_clamps_at_xl(self) -> None:
        assert _bump_tier(SizeTier.M, 10) == SizeTier.XL

    def test_epic_keyword_already_at_xl_no_bump_needed(self) -> None:
        result = classify_task("Massive rewrite of the entire auth system")
        assert result.tier == SizeTier.XL
