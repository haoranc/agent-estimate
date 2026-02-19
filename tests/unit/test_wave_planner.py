"""Tests for wave planner — DAG validation, topo sort, LPT bin packing."""

from __future__ import annotations

import pytest

from agent_estimate.core.models import AgentProfile, TaskNode
from agent_estimate.core.wave_planner import plan_waves


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(
    task_id: str,
    duration: float = 30.0,
    deps: tuple[str, ...] = (),
    caps: tuple[str, ...] = (),
) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        duration_minutes=duration,
        dependencies=deps,
        required_capabilities=caps,
    )


def _agent(
    name: str = "claude",
    caps: list[str] | None = None,
    parallelism: int = 1,
) -> AgentProfile:
    return AgentProfile(
        name=name,
        capabilities=caps or ["code"],
        parallelism=parallelism,
        cost_per_turn=0.0,
        model_tier="opus",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLinearChain:
    """A→B→C should produce 3 waves in correct order."""

    def test_linear_chain(self) -> None:
        tasks = [
            _node("A", 10),
            _node("B", 20, deps=("A",)),
            _node("C", 15, deps=("B",)),
        ]
        plan = plan_waves(tasks, [_agent()])

        assert len(plan.waves) == 3
        wave_tasks = [
            [a.task_id for a in w.assignments] for w in plan.waves
        ]
        assert wave_tasks == [["A"], ["B"], ["C"]]


class TestFanOutFanIn:
    """A→{B,C,D}→E: B/C/D should land in the same wave."""

    def test_fan_out_fan_in(self) -> None:
        tasks = [
            _node("A", 10),
            _node("B", 20, deps=("A",)),
            _node("C", 25, deps=("A",)),
            _node("D", 15, deps=("A",)),
            _node("E", 10, deps=("B", "C", "D")),
        ]
        agents = [_agent(parallelism=3)]
        plan = plan_waves(tasks, agents)

        # Wave 0: A, Wave 1: B/C/D, Wave 2: E
        assert len(plan.waves) == 3
        mid_wave_tasks = sorted(a.task_id for a in plan.waves[1].assignments)
        assert mid_wave_tasks == ["B", "C", "D"]


class TestCycleDetection:
    """A→B→A should raise ValueError with cycle info including closing node."""

    def test_cycle_detection(self) -> None:
        tasks = [
            _node("A", 10, deps=("B",)),
            _node("B", 10, deps=("A",)),
        ]
        with pytest.raises(ValueError, match=r"A -> B -> A|B -> A -> B"):
            plan_waves(tasks, [_agent()])


class TestSingleAgent:
    """All independent tasks with 1 agent slot → all in one wave, sequential."""

    def test_single_agent(self) -> None:
        tasks = [_node("A", 10), _node("B", 20), _node("C", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)])

        # All tasks in a single generation (no deps) → 1 wave
        assert len(plan.waves) == 1
        # Wave makespan = sum of durations (all in one bin)
        assert plan.waves[0].end_minutes == pytest.approx(60.0)


class TestUnbalancedLoad:
    """LPT should produce better balance than naive assignment."""

    def test_unbalanced_load(self) -> None:
        # Durations: 40, 30, 20, 10 → LPT with 2 bins:
        # Bin 0: 40 + 10 = 50, Bin 1: 30 + 20 = 50 → makespan 50
        # Naive sequential: 40, 30 → bin0=70, 20, 10 → bin1=30 → makespan 70
        tasks = [
            _node("A", 40),
            _node("B", 30),
            _node("C", 20),
            _node("D", 10),
        ]
        plan = plan_waves(tasks, [_agent(parallelism=2)])

        assert len(plan.waves) == 1
        # LPT optimal makespan is 50
        assert plan.waves[0].end_minutes == pytest.approx(50.0)


class TestCapabilityFiltering:
    """Task requiring a specific cap is assigned to the capable agent."""

    def test_capability_filtering(self) -> None:
        tasks = [_node("A", 30, caps=("deploy",))]
        agents = [
            _agent("coder", caps=["code"]),
            _agent("deployer", caps=["code", "deploy"]),
        ]
        plan = plan_waves(tasks, agents)

        assert plan.waves[0].assignments[0].agent_name == "deployer"


class TestNoEligibleAgent:
    """Task requires cap no agent has → ValueError."""

    def test_no_eligible_agent(self) -> None:
        tasks = [_node("A", 30, caps=("magic",))]
        agents = [_agent("coder", caps=["code"])]

        with pytest.raises(ValueError, match="No eligible agent"):
            plan_waves(tasks, agents)


class TestCriticalPath:
    """Verify critical path identification on a diamond DAG."""

    def test_critical_path(self) -> None:
        # Diamond: A→B(40), A→C(10), B→D, C→D
        # Critical path: A→B→D
        tasks = [
            _node("A", 10),
            _node("B", 40, deps=("A",)),
            _node("C", 10, deps=("A",)),
            _node("D", 5, deps=("B", "C")),
        ]
        plan = plan_waves(tasks, [_agent(parallelism=2)])

        assert plan.critical_path == ("A", "B", "D")
        assert plan.critical_path_minutes == pytest.approx(55.0)


class TestUtilizationMetrics:
    """Check per-agent utilization and parallel efficiency values."""

    def test_utilization_metrics(self) -> None:
        # 2 independent tasks: A(60), B(40), 2 agent slots → 1 wave, makespan 60
        tasks = [_node("A", 60), _node("B", 40)]
        agents = [_agent("alpha"), _agent("beta")]
        plan = plan_waves(tasks, agents, inter_wave_overhead_hours=0)

        assert plan.total_wall_clock_minutes == pytest.approx(60.0)
        assert plan.total_sequential_minutes == pytest.approx(100.0)
        # parallel_efficiency = 100 / (2 slots * 60 wall) = 100/120 ≈ 0.833
        assert plan.parallel_efficiency == pytest.approx(100.0 / 120.0)

        # Agent with the 60-min task: 60/60 = 1.0
        # Agent with the 40-min task: 40/60 ≈ 0.667
        utils = plan.agent_utilization
        assert max(utils.values()) == pytest.approx(1.0)
        assert min(utils.values()) == pytest.approx(40.0 / 60.0)


class TestInterWaveOverhead:
    """Verify overhead is added between waves but not after the last."""

    def test_inter_wave_overhead(self) -> None:
        # A→B, each 30 min, overhead = 0.5h = 30 min
        tasks = [
            _node("A", 30),
            _node("B", 30, deps=("A",)),
        ]
        plan = plan_waves(tasks, [_agent()], inter_wave_overhead_hours=0.5)

        assert len(plan.waves) == 2
        # Wave 0: 0–30
        assert plan.waves[0].start_minutes == pytest.approx(0.0)
        assert plan.waves[0].end_minutes == pytest.approx(30.0)
        # Wave 1: 60–90 (30 min overhead gap)
        assert plan.waves[1].start_minutes == pytest.approx(60.0)
        assert plan.waves[1].end_minutes == pytest.approx(90.0)
        # Total wall clock = end of last wave
        assert plan.total_wall_clock_minutes == pytest.approx(90.0)


class TestInterWaveOverheadZero:
    """Overhead=0 produces contiguous waves with no gap."""

    def test_zero_overhead(self) -> None:
        tasks = [
            _node("A", 30),
            _node("B", 20, deps=("A",)),
        ]
        plan = plan_waves(tasks, [_agent()], inter_wave_overhead_hours=0)

        assert len(plan.waves) == 2
        assert plan.waves[1].start_minutes == pytest.approx(plan.waves[0].end_minutes)
        assert plan.total_wall_clock_minutes == pytest.approx(50.0)


class TestUnknownDependency:
    """Referencing a non-existent task ID raises ValueError."""

    def test_unknown_dep_raises(self) -> None:
        tasks = [_node("A", 10, deps=("GHOST",))]
        with pytest.raises(ValueError, match="unknown task"):
            plan_waves(tasks, [_agent()])


class TestNoAgents:
    """Empty agents list raises ValueError."""

    def test_no_agents_raises(self) -> None:
        tasks = [_node("A", 10)]
        with pytest.raises(ValueError, match="At least one agent"):
            plan_waves(tasks, [])


class TestNegativeOverhead:
    """Negative overhead raises ValueError."""

    def test_negative_overhead_raises(self) -> None:
        with pytest.raises(ValueError, match="inter_wave_overhead_hours"):
            plan_waves([_node("A", 10)], [_agent()], inter_wave_overhead_hours=-0.5)


class TestEmptyInput:
    """Empty task list returns a zero-valued plan."""

    def test_empty_tasks(self) -> None:
        plan = plan_waves([], [_agent()])

        assert plan.waves == ()
        assert plan.critical_path == ()
        assert plan.total_wall_clock_minutes == pytest.approx(0.0)
        assert plan.total_sequential_minutes == pytest.approx(0.0)
