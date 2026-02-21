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
    """All independent tasks with 1 agent slot → all in one wave, co-dispatched."""

    def test_single_agent(self) -> None:
        tasks = [_node("A", 10), _node("B", 20), _node("C", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)])

        # All tasks in a single generation (no deps) → 1 wave
        assert len(plan.waves) == 1
        # LPT order: C(30), B(20), A(10) — 3 tasks on same agent → co-dispatch
        # C is first (no reduction), B and A get 0.5x: 30 + 10 + 5 = 45
        assert plan.waves[0].end_minutes == pytest.approx(45.0)


class TestUnbalancedLoad:
    """LPT should produce better balance than naive assignment.

    With co-dispatch: all 4 tasks land on the same agent across 2 slots.
    LPT assigns A(40)→slot0, B(30)→slot1, C(20)→slot1, D(10)→slot0.
    agent_wave_tasks['claude'] = ['A', 'B', 'C', 'D'] — A is first (no reduction),
    B, C, D get 0.5x: B=15, C=10, D=5.
    Revised slot loads: slot0=A(40)+D(5)=45, slot1=B(15)+C(10)=25 → makespan=45.
    """

    def test_unbalanced_load(self) -> None:
        # Durations: 40, 30, 20, 10 → LPT with 2 bins (same agent, parallelism=2)
        tasks = [
            _node("A", 40),
            _node("B", 30),
            _node("C", 20),
            _node("D", 10),
        ]
        plan = plan_waves(tasks, [_agent(parallelism=2)])

        assert len(plan.waves) == 1
        # Co-dispatch reduces B, C, D by 0.5x; makespan = slot0 = 40+5 = 45
        assert plan.waves[0].end_minutes == pytest.approx(45.0)


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


class TestCoDispatchTwoTasks:
    """2 tasks on the same agent → second gets 0.5x warm context reduction."""

    def test_second_task_reduced(self) -> None:
        # Single agent with parallelism=1; both tasks land in the same slot.
        tasks = [_node("A", 40), _node("B", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        by_id = {a.task_id: a for a in wave.assignments}

        # First task: no reduction
        assert by_id["A"].duration_minutes == pytest.approx(40.0)
        # Second task: 0.5x → 15 min
        assert by_id["B"].duration_minutes == pytest.approx(15.0)

    def test_co_dispatch_group_populated(self) -> None:
        tasks = [_node("A", 40), _node("B", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        by_id = {a.task_id: a for a in wave.assignments}

        # Both tasks should share the same co_dispatch_group tuple
        assert set(by_id["A"].co_dispatch_group) == {"A", "B"}
        assert set(by_id["B"].co_dispatch_group) == {"A", "B"}

    def test_wave_makespan_uses_adjusted_durations(self) -> None:
        # With 1 slot: A(40) + B(30*0.5=15) = 55 min makespan
        tasks = [_node("A", 40), _node("B", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        assert plan.waves[0].end_minutes == pytest.approx(55.0)


class TestCoDispatchThreeTasks:
    """3 tasks on the same agent → 2nd and 3rd both get 0.5x reduction."""

    def test_third_task_also_reduced(self) -> None:
        tasks = [_node("A", 60), _node("B", 40), _node("C", 20)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        by_id = {a.task_id: a for a in wave.assignments}

        assert by_id["A"].duration_minutes == pytest.approx(60.0)
        assert by_id["B"].duration_minutes == pytest.approx(20.0)  # 40 * 0.5
        assert by_id["C"].duration_minutes == pytest.approx(10.0)  # 20 * 0.5

    def test_three_task_group_membership(self) -> None:
        tasks = [_node("A", 60), _node("B", 40), _node("C", 20)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        by_id = {a.task_id: a for a in wave.assignments}

        for tid in ("A", "B", "C"):
            assert set(by_id[tid].co_dispatch_group) == {"A", "B", "C"}


class TestCoDispatchDifferentAgents:
    """Tasks on different agents → no co-dispatch reduction."""

    def test_no_reduction_across_agents(self) -> None:
        tasks = [_node("A", 30), _node("B", 30)]
        agents = [_agent("alpha"), _agent("beta")]
        plan = plan_waves(tasks, agents, inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        by_id = {a.task_id: a for a in wave.assignments}

        # Each task goes to a different agent → no co-dispatch
        assert by_id["A"].duration_minutes == pytest.approx(30.0)
        assert by_id["B"].duration_minutes == pytest.approx(30.0)
        assert by_id["A"].co_dispatch_group == ()
        assert by_id["B"].co_dispatch_group == ()


class TestCoDispatchSingleTask:
    """Single task per agent → no co-dispatch, no group set."""

    def test_single_task_no_group(self) -> None:
        tasks = [_node("A", 30)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        assert wave.assignments[0].co_dispatch_group == ()
        assert wave.assignments[0].duration_minutes == pytest.approx(30.0)


class TestCoDispatchMixedWaves:
    """Co-dispatch in wave 0 but solo in wave 1 — only wave 0 tasks are flagged."""

    def test_mixed_waves(self) -> None:
        # Wave 0: A + B on same agent; Wave 1: C alone (depends on A and B)
        tasks = [
            _node("A", 30),
            _node("B", 20),
            _node("C", 25, deps=("A", "B")),
        ]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        # Wave 0 assignments
        wave0_by_id = {a.task_id: a for a in plan.waves[0].assignments}
        assert set(wave0_by_id["A"].co_dispatch_group) == {"A", "B"}
        assert set(wave0_by_id["B"].co_dispatch_group) == {"A", "B"}

        # Wave 1: C is alone — no co-dispatch
        wave1_by_id = {a.task_id: a for a in plan.waves[1].assignments}
        assert wave1_by_id["C"].co_dispatch_group == ()
        assert wave1_by_id["C"].duration_minutes == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# Batch review amortization tests
# ---------------------------------------------------------------------------


def _rnode(
    task_id: str,
    duration: float = 30.0,
    review: float = 15.0,
    deps: tuple[str, ...] = (),
) -> TaskNode:
    """Helper: TaskNode with explicit work + review minutes."""
    return TaskNode(
        task_id=task_id,
        duration_minutes=duration,
        review_minutes=review,
        dependencies=deps,
    )


class TestBatchReviewSingleAgentTwoTasks:
    """Two tasks on one agent: wave makespan = sum(work) + single_review_cycle."""

    def test_makespan_amortized(self) -> None:
        # Task A: 40 work + 15 review; Task B: 30 work + 15 review
        # Naive: (40+15) + (30+15) = 100m
        # Amortized: 40 + 30*0.5 (co-dispatch) + 15 (single review) = 70m
        tasks = [_rnode("A", 40, 15), _rnode("B", 30, 15)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        # Co-dispatch: A=40 (first), B=15 (0.5x); amortized review = 15
        # Leading slot load = 40, after review = 55
        # Slot load (A+B adjusted): 40 + 15 = 55; plus review 15 → wave makespan 70
        assert plan.waves[0].end_minutes == pytest.approx(70.0)

    def test_agent_review_minutes_populated(self) -> None:
        tasks = [_rnode("A", 40, 15), _rnode("B", 30, 15)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        assert "claude" in wave.agent_review_minutes
        assert wave.agent_review_minutes["claude"] == pytest.approx(15.0)

    def test_total_sequential_uses_amortized_review(self) -> None:
        # Sequential baseline = sum(work) + amortized review per agent per wave
        # = (40 + 30) + 1 review cycle of 15 = 85
        # (not per-task: (40+15) + (30+15) = 100)
        tasks = [_rnode("A", 40, 15), _rnode("B", 30, 15)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        assert plan.total_sequential_minutes == pytest.approx(85.0)


class TestBatchReviewNoReviewOverhead:
    """When review_minutes=0, wave makespan is unchanged from work-only."""

    def test_zero_review_unchanged(self) -> None:
        tasks = [
            TaskNode("A", duration_minutes=40, review_minutes=0.0),
            TaskNode("B", duration_minutes=30, review_minutes=0.0),
        ]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        # Co-dispatch: A=40, B=15; no review → 55
        assert plan.waves[0].end_minutes == pytest.approx(55.0)
        assert plan.waves[0].agent_review_minutes["claude"] == pytest.approx(0.0)


class TestBatchReviewSingleTask:
    """Single task per agent: full review cycle still charged."""

    def test_single_task_full_review(self) -> None:
        tasks = [_rnode("A", 30, 15)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        # Work=30 + review=15 = 45
        assert plan.waves[0].end_minutes == pytest.approx(45.0)
        assert plan.waves[0].agent_review_minutes["claude"] == pytest.approx(15.0)


class TestBatchReviewTwoAgentsTwoTasks:
    """One task per agent: each agent pays its own review cycle."""

    def test_two_agents_independent_review(self) -> None:
        tasks = [_rnode("A", 30, 15), _rnode("B", 40, 15)]
        agents = [_agent("alpha"), _agent("beta")]
        plan = plan_waves(tasks, agents, inter_wave_overhead_hours=0)

        wave = plan.waves[0]
        # alpha: A(30+15=45), beta: B(40+15=55) → makespan = 55
        assert wave.end_minutes == pytest.approx(55.0)
        assert wave.agent_review_minutes["alpha"] == pytest.approx(15.0)
        assert wave.agent_review_minutes["beta"] == pytest.approx(15.0)


class TestBatchReviewThreeTasksSameAgent:
    """Three tasks on one agent: only one review cycle, not three."""

    def test_three_tasks_single_review(self) -> None:
        # Tasks: A=60w, B=40w, C=20w — all same agent, review=15 each
        # Co-dispatch: A=60 (first), B=20 (0.5x), C=10 (0.5x)
        # Slot total work = 60 + 20 + 10 = 90; plus single review 15 → 105
        tasks = [_rnode("A", 60, 15), _rnode("B", 40, 15), _rnode("C", 20, 15)]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        assert plan.waves[0].end_minutes == pytest.approx(105.0)
        assert plan.waves[0].agent_review_minutes["claude"] == pytest.approx(15.0)


class TestBatchReviewAcrossWaves:
    """Each wave charges its own amortized review independently."""

    def test_review_per_wave(self) -> None:
        # Wave 0: A(30w, 15r); Wave 1: B(20w, 15r) depends on A
        tasks = [_rnode("A", 30, 15), _rnode("B", 20, 15, deps=("A",))]
        plan = plan_waves(tasks, [_agent(parallelism=1)], inter_wave_overhead_hours=0)

        assert len(plan.waves) == 2
        # Wave 0: 30 + 15 = 45
        assert plan.waves[0].end_minutes == pytest.approx(45.0)
        # Wave 1: starts at 45; 20 + 15 = 35; ends at 80
        assert plan.waves[1].end_minutes == pytest.approx(80.0)
        assert plan.waves[0].agent_review_minutes["claude"] == pytest.approx(15.0)
        assert plan.waves[1].agent_review_minutes["claude"] == pytest.approx(15.0)
