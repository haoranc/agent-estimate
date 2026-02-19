"""Tests for core/human_comparison.py — all task types."""

from __future__ import annotations

import math

import pytest

from agent_estimate.core.human_comparison import compute_human_equivalent, get_human_multiplier
from agent_estimate.core.models import TaskType


# Expected geometric-mean multipliers from _HUMAN_MULTIPLIERS
_EXPECTED_MULTIPLIERS: dict[TaskType, tuple[float, float]] = {
    TaskType.BOILERPLATE: (3.0, 5.0),
    TaskType.BUG_FIX: (1.5, 3.0),
    TaskType.FEATURE: (2.0, 4.0),
    TaskType.REFACTOR: (2.0, 3.5),
    TaskType.TEST: (2.5, 4.5),
    TaskType.DOCS: (3.0, 6.0),
    TaskType.UNKNOWN: (2.0, 4.0),
}


class TestGetHumanMultiplier:
    @pytest.mark.parametrize("task_type,expected_range", list(_EXPECTED_MULTIPLIERS.items()))
    def test_multiplier_is_geometric_mean(
        self, task_type: TaskType, expected_range: tuple[float, float]
    ) -> None:
        lo, hi = expected_range
        expected = math.sqrt(lo * hi)
        assert get_human_multiplier(task_type) == pytest.approx(expected)

    def test_all_task_types_covered(self) -> None:
        for task_type in TaskType:
            mult = get_human_multiplier(task_type)
            assert mult > 1.0, f"{task_type} multiplier should be > 1.0"

    def test_boilerplate_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.BOILERPLATE) == pytest.approx(math.sqrt(15.0))

    def test_bug_fix_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.BUG_FIX) == pytest.approx(math.sqrt(4.5))

    def test_feature_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.FEATURE) == pytest.approx(math.sqrt(8.0))

    def test_refactor_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.REFACTOR) == pytest.approx(math.sqrt(7.0))

    def test_test_task_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.TEST) == pytest.approx(math.sqrt(11.25))

    def test_docs_multiplier_value(self) -> None:
        assert get_human_multiplier(TaskType.DOCS) == pytest.approx(math.sqrt(18.0))

    def test_unknown_multiplier_equals_feature(self) -> None:
        assert get_human_multiplier(TaskType.UNKNOWN) == pytest.approx(
            get_human_multiplier(TaskType.FEATURE)
        )


class TestComputeHumanEquivalent:
    def test_feature_type(self) -> None:
        agent_min = 30.0
        result = compute_human_equivalent(agent_min, TaskType.FEATURE)
        assert result == pytest.approx(agent_min * math.sqrt(8.0))

    def test_bug_fix_type(self) -> None:
        agent_min = 60.0
        result = compute_human_equivalent(agent_min, TaskType.BUG_FIX)
        assert result == pytest.approx(60.0 * math.sqrt(4.5))

    def test_boilerplate_type(self) -> None:
        agent_min = 10.0
        result = compute_human_equivalent(agent_min, TaskType.BOILERPLATE)
        assert result == pytest.approx(10.0 * math.sqrt(15.0))

    def test_refactor_type(self) -> None:
        agent_min = 45.0
        result = compute_human_equivalent(agent_min, TaskType.REFACTOR)
        assert result == pytest.approx(45.0 * math.sqrt(7.0))

    def test_test_type(self) -> None:
        agent_min = 20.0
        result = compute_human_equivalent(agent_min, TaskType.TEST)
        assert result == pytest.approx(20.0 * math.sqrt(11.25))

    def test_docs_type(self) -> None:
        agent_min = 15.0
        result = compute_human_equivalent(agent_min, TaskType.DOCS)
        assert result == pytest.approx(15.0 * math.sqrt(18.0))

    def test_unknown_type(self) -> None:
        agent_min = 25.0
        result = compute_human_equivalent(agent_min, TaskType.UNKNOWN)
        assert result == pytest.approx(25.0 * math.sqrt(8.0))

    def test_zero_agent_minutes(self) -> None:
        result = compute_human_equivalent(0.0, TaskType.FEATURE)
        assert result == pytest.approx(0.0)

    def test_human_equivalent_always_greater_than_agent(self) -> None:
        for task_type in TaskType:
            result = compute_human_equivalent(100.0, task_type)
            assert result > 100.0
