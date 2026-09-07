"""Assigned-profile adjustments preserve scheduling and report arithmetic."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from agent_estimate.adapters.config_loader import _coerce_plugin_profile
from agent_estimate.cli.commands import _pipeline
from agent_estimate.core.models import (
    AgentProfile,
    EstimationConfig,
    PertResult,
    ProjectSettings,
    TaskEstimate,
    TaskNode,
)
from agent_estimate.core.modifiers import build_modifier_set
from agent_estimate.core.sizing import classify_task
from agent_estimate.core.wave_planner import plan_waves


def _estimate(minutes):
    return TaskEstimate(
        sizing=classify_task("Implement a feature"),
        pert=PertResult(minutes / 2, minutes, minutes * 1.5, minutes, minutes / 6),
        modifiers=build_modifier_set(),
        review_minutes=15,
        total_expected_minutes=minutes + 15,
        human_equivalent_minutes=minutes * 8,
        metr_warning=None,
    )


def _config(*agents, friction=1.0, overhead=0.0):
    return EstimationConfig(agents=list(agents), settings=ProjectSettings(
        friction_multiplier=friction, inter_wave_overhead=overhead, metr_fallback_threshold=45,
    ))


def _agent(name="A", factor=1.0, parallelism=1):
    return AgentProfile(
        name=name, capabilities=["code"], parallelism=parallelism,
        cost_per_turn=1, model_tier="unknown", estimate_multiplier=factor,
    )


class _Plugin:
    capabilities = ("code",)
    cost_per_turn = 1
    model_tier = "unknown"

    def __init__(self, name, factor, parallelism=1):
        self.name = name
        self.factor = factor
        self.parallelism = parallelism
        self.calls = []

    def adjust_estimate(self, minutes):
        self.calls.append(minutes)
        return minutes * self.factor


def test_selected_hooks_run_once_without_reassignment_and_recompute_all_metrics(monkeypatch):
    first, second, idle = _Plugin("A", 0.5, 2), _Plugin("B", 3), _Plugin("Idle", 99)
    idle.capabilities = ("unused",)
    agents = [_coerce_plugin_profile(plugin, plugin.name) for plugin in (first, second, idle)]
    planner = Mock(wraps=plan_waves)
    build_report = Mock(wraps=_pipeline._build_report)
    monkeypatch.setattr(_pipeline, "plan_waves", planner)
    monkeypatch.setattr(_pipeline, "_build_report", build_report)
    monkeypatch.setattr(_pipeline, "_estimate_by_category", lambda category, desc, *a, **k: (
        _estimate(float(desc)), [],
    ))
    report = _pipeline.run_estimate_pipeline(
        ["40", "30", "20", "10"], _config(*agents), required_capabilities=("code",),
    )

    assert planner.call_count == 1
    assert [p.calls for p in (first, second, idle)] == [[40, 20, 10], [30], []]
    estimates, plan = build_report.call_args.args[1:3]
    assignments = plan.waves[0].assignments
    assert [(a.agent_name, a.slot_index) for a in assignments] == [
        ("A", 0), ("B", 0), ("A", 1), ("A", 1),
    ]
    assert [a.duration_minutes for a in assignments] == [20, 90, 10, 2.5]
    assert assignments[-1].co_dispatch_group == ("2", "3")
    assert plan.total_wall_clock_minutes == 105
    assert plan.total_sequential_minutes == 155
    assert plan.critical_path == ("1",)
    assert plan.critical_path_minutes == 90
    assert dict(plan.agent_utilization) == pytest.approx({
        "A": 32.5 / 210, "B": 90 / 105, "Idle": 0,
    })
    assert plan.parallel_efficiency == pytest.approx(155 / 420)
    assert [estimate.pert.expected for estimate in estimates] == [20, 90, 10, 5]
    assert estimates[1].pert == PertResult(45, 90, 135, 90, 15)
    assert all(estimate.review_minutes == 15 for estimate in estimates)
    assert [estimate.human_equivalent_minutes for estimate in estimates] == [320, 240, 160, 80]
    assert report.timeline.expected_case_minutes == 105
    assert report.timeline.best_case_minutes < 105 < report.timeline.worst_case_minutes
    assert report.timeline.human_equivalent_minutes == 800
    assert [(load.total_work_minutes, load.heuristic_cost) for load in report.agent_load] == [
        (32.5, 6.5), (90, 18), (0, 0),
    ]
    assert report.tasks[0].metr_warning is None
    assert "90.0m" in report.tasks[1].metr_warning


def test_adjustment_preserves_review_and_inter_wave_gap():
    agent = _agent(factor=2.0)
    nodes = [TaskNode("0", 40, review_minutes=15), TaskNode("1", 10, ("0",), review_minutes=15)]
    original = plan_waves(nodes, [agent], inter_wave_overhead_hours=7 / 60)
    estimates, plan = _pipeline._adjust_assigned_estimates(
        [_estimate(40), _estimate(10)], nodes, original, _config(agent),
    )
    assert [(w.start_minutes, w.end_minutes) for w in plan.waves] == [(0, 95), (102, 137)]
    assert plan.critical_path == ("0", "1")
    assert plan.critical_path_minutes == 100
    assert plan.total_sequential_minutes == 130
    assert estimates[0].total_expected_minutes == 95


def test_identity_adjustment_keeps_original_objects():
    agent = _agent()
    nodes = [TaskNode("0", 40, review_minutes=15)]
    original = plan_waves(nodes, [agent])
    estimates = [_estimate(40)]
    new_estimates, new_plan = _pipeline._adjust_assigned_estimates(estimates, nodes, original, _config(agent))
    assert new_estimates is estimates
    assert new_plan is original


@pytest.mark.parametrize("result", [float("nan"), float("inf"), -1, 0, True, "80", None, 10**1000])
def test_invalid_plugin_result_is_an_estimation_error(result):
    plugin = _Plugin("A", 1)
    plugin.adjust_estimate = lambda minutes: result
    agent = _coerce_plugin_profile(plugin, "A")
    nodes = [TaskNode("0", 40)]
    with pytest.raises(ValueError, match="adjust_estimate must return"):
        _pipeline._adjust_assigned_estimates([_estimate(40)], nodes, plan_waves(nodes, [agent]), _config(agent))


def test_plugin_exception_is_an_estimation_error():
    plugin = _Plugin("A", 1)

    def fail(minutes):
        raise RuntimeError("plugin failed")

    plugin.adjust_estimate = fail
    agent = _coerce_plugin_profile(plugin, "A")
    nodes = [TaskNode("0", 40)]
    with pytest.raises(ValueError, match="adjust_estimate failed: plugin failed"):
        _pipeline._adjust_assigned_estimates([_estimate(40)], nodes, plan_waves(nodes, [agent]), _config(agent))


def test_zero_work_cannot_become_nonzero_through_a_scalar_hook():
    plugin = _Plugin("A", 1)
    plugin.adjust_estimate = lambda minutes: 1
    agent = _coerce_plugin_profile(plugin, "A")
    nodes = [TaskNode("0", 0)]
    with pytest.raises(ValueError, match="zero for zero work"):
        _pipeline._adjust_assigned_estimates([_estimate(0)], nodes, plan_waves(nodes, [agent]), _config(agent))


@pytest.mark.parametrize("overflow", ["pert", "wave"])
def test_finite_hook_result_cannot_overflow_other_forecast_fields(overflow):
    agent = _agent(factor=1e307)
    estimate = _estimate(10)
    if overflow == "pert":
        estimate = replace(estimate, pert=replace(estimate.pert, pessimistic=100))
    nodes = [TaskNode("0", 100 if overflow == "wave" else 10)]
    with pytest.raises(ValueError, match="overflowed"):
        _pipeline._adjust_assigned_estimates([estimate], nodes, plan_waves(nodes, [agent]), _config(agent))


@pytest.mark.parametrize("overflow", ["timeline", "heuristic cost"])
def test_finite_adjusted_tasks_cannot_emit_infinite_report_values(monkeypatch, overflow):
    agent = _agent(factor=1e306 if overflow == "timeline" else 1e100, parallelism=3)
    if overflow == "heuristic cost":
        agent = agent.model_copy(update={"cost_per_turn": 1e305})
    monkeypatch.setattr(_pipeline, "_estimate_by_category", lambda *a, **k: (_estimate(40), []))
    with pytest.raises(ValueError, match=f"overflowed the .*{overflow}"):
        _pipeline.run_estimate_pipeline(["task 1", "task 2", "task 3"], _config(agent))
