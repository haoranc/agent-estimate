"""Tests for the Markdown report renderer."""

from __future__ import annotations

import pytest

from agent_estimate.core.models import (
    MetrWarning,
    ModifierSet,
    PertResult,
    SizeTier,
    SizingResult,
    TaskEstimate,
    TaskType,
)
from agent_estimate.render.markdown_report import render_markdown_report
from agent_estimate.render.report_models import (
    EstimationReport,
    ReportAgentLoad,
    ReportTask,
    ReportTimeline,
    ReportWave,
)


def _make_task_estimate(
    *,
    tier: SizeTier,
    base: tuple[float, float, float],
    adjusted: tuple[float, float, float],
    modifier_set: ModifierSet,
    review_minutes: float,
    human_equivalent_minutes: float | None,
    metr_warning: MetrWarning | None,
) -> TaskEstimate:
    o, m, p = base
    ao, am, ap = adjusted
    expected = (ao + 4 * am + ap) / 6
    return TaskEstimate(
        sizing=SizingResult(
            tier=tier,
            baseline_optimistic=o,
            baseline_most_likely=m,
            baseline_pessimistic=p,
            task_type=TaskType.FEATURE,
            signals=("test",),
        ),
        pert=PertResult(
            optimistic=ao,
            most_likely=am,
            pessimistic=ap,
            expected=expected,
            sigma=(ap - ao) / 6,
        ),
        modifiers=modifier_set,
        review_minutes=review_minutes,
        total_expected_minutes=expected + review_minutes,
        human_equivalent_minutes=human_equivalent_minutes,
        metr_warning=metr_warning,
    )


def test_report_task_from_estimate_maps_fields() -> None:
    warning = MetrWarning(
        model_key="opus",
        threshold_minutes=90.0,
        estimated_minutes=120.0,
        message="Estimate exceeds threshold",
    )
    estimate = _make_task_estimate(
        tier=SizeTier.M,
        base=(25.0, 50.0, 90.0),
        adjusted=(30.0, 60.0, 108.0),
        modifier_set=ModifierSet(
            spec_clarity=1.2,
            warm_context=1.0,
            agent_fit=1.1,
            combined=1.32,
        ),
        review_minutes=17.5,
        human_equivalent_minutes=220.0,
        metr_warning=warning,
    )

    row = ReportTask.from_estimate(name="Implement auth", agent="Codex", estimate=estimate)

    assert row.name == "Implement auth"
    assert row.tier == "M"
    assert row.base_pert_expected_minutes == pytest.approx((25.0 + 4 * 50.0 + 90.0) / 6)
    assert row.effective_duration_minutes == pytest.approx((30.0 + 4 * 60.0 + 108.0) / 6)
    assert row.review_overhead_minutes == pytest.approx(17.5)
    assert row.metr_warning == "Estimate exceeds threshold"


def test_render_markdown_report_contains_required_sections() -> None:
    task_a = ReportTask.from_estimate(
        name="Implement auth",
        agent="Codex",
        estimate=_make_task_estimate(
            tier=SizeTier.M,
            base=(25.0, 50.0, 90.0),
            adjusted=(27.5, 55.0, 99.0),
            modifier_set=ModifierSet(
                spec_clarity=1.1,
                warm_context=1.0,
                agent_fit=1.0,
                combined=1.1,
            ),
            review_minutes=17.5,
            human_equivalent_minutes=160.0,
            metr_warning=MetrWarning(
                model_key="opus",
                threshold_minutes=90.0,
                estimated_minutes=110.0,
                message="Estimate exceeds threshold",
            ),
        ),
    )
    task_b = ReportTask.from_estimate(
        name="Add tests",
        agent="Claude",
        estimate=_make_task_estimate(
            tier=SizeTier.S,
            base=(12.0, 23.0, 40.0),
            adjusted=(12.0, 23.0, 40.0),
            modifier_set=ModifierSet(
                spec_clarity=1.0,
                warm_context=1.0,
                agent_fit=1.0,
                combined=1.0,
            ),
            review_minutes=7.5,
            human_equivalent_minutes=75.0,
            metr_warning=None,
        ),
    )
    report = EstimationReport(
        title="W3 Estimate",
        tasks=(task_a, task_b),
        waves=(
            ReportWave(
                number=1,
                tasks=("Implement auth", "Add tests"),
                duration_minutes=85.0,
                agent_assignments={
                    "Codex": ("Implement auth",),
                    "Claude": ("Add tests",),
                },
            ),
        ),
        timeline=ReportTimeline(
            best_case_minutes=70.0,
            expected_case_minutes=90.0,
            worst_case_minutes=130.0,
            human_equivalent_minutes=250.0,
        ),
        agent_load=(
            ReportAgentLoad(
                agent="Codex",
                task_count=1,
                total_work_minutes=72.5,
                estimated_cost=18.40,
            ),
            ReportAgentLoad(
                agent="Claude",
                task_count=1,
                total_work_minutes=30.5,
                estimated_cost=9.30,
            ),
        ),
        critical_path=("Implement auth", "Add tests"),
    )

    rendered = render_markdown_report(report)

    assert "# W3 Estimate" in rendered
    assert "## Per-Task Estimates" in rendered
    assert "## Wave Plan" in rendered
    assert "## Timeline Summary" in rendered
    assert "## Agent Load Summary" in rendered
    assert "## Critical Path" in rendered
    assert "## METR Warnings" in rendered
    assert "| Review overhead (additive) | 25m |" in rendered
    assert "| **Total** | **25m** |" in rendered
    assert "**Implement auth**" in rendered
    assert "Claude: Add tests; Codex: Implement auth" in rendered
    assert "Compression ratio | 2.78x" in rendered
    assert "Estimate exceeds threshold" in rendered


def test_render_markdown_report_handles_empty_path_and_warnings() -> None:
    task = ReportTask.from_estimate(
        name="Docs cleanup",
        agent="Codex",
        estimate=_make_task_estimate(
            tier=SizeTier.XS,
            base=(5.0, 10.0, 20.0),
            adjusted=(5.0, 10.0, 20.0),
            modifier_set=ModifierSet(
                spec_clarity=1.0,
                warm_context=1.0,
                agent_fit=1.0,
                combined=1.0,
            ),
            review_minutes=0.0,
            human_equivalent_minutes=None,
            metr_warning=None,
        ),
    )
    report = EstimationReport(
        tasks=(task,),
        waves=(),
        timeline=ReportTimeline(
            best_case_minutes=5.0,
            expected_case_minutes=10.0,
            worst_case_minutes=20.0,
            human_equivalent_minutes=30.0,
        ),
        agent_load=(),
        critical_path=(),
    )

    rendered = render_markdown_report(report)

    assert "No critical path provided." in rendered
    assert "No METR threshold warnings." in rendered
