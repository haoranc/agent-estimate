"""Shared report data models for renderers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent_estimate.core.models import TaskEstimate


@dataclass(frozen=True)
class ReportTask:
    """Flattened per-task report row for renderers."""

    name: str
    tier: str
    agent: str
    base_pert_optimistic_minutes: float
    base_pert_most_likely_minutes: float
    base_pert_pessimistic_minutes: float
    modifier_spec_clarity: float
    modifier_warm_context: float
    modifier_agent_fit: float
    modifier_combined: float
    effective_duration_minutes: float
    human_equivalent_minutes: float | None
    review_overhead_minutes: float
    metr_warning: str | None = None
    warm_context_detail: str | None = None
    tier_correction_warnings: tuple[str, ...] = ()

    @property
    def base_pert_expected_minutes(self) -> float:
        """Return expected minutes for the unmodified base PERT tuple."""
        return (
            self.base_pert_optimistic_minutes
            + (4 * self.base_pert_most_likely_minutes)
            + self.base_pert_pessimistic_minutes
        ) / 6

    @classmethod
    def from_estimate(cls, *, name: str, agent: str, estimate: TaskEstimate) -> "ReportTask":
        """Construct a report row from a TaskEstimate."""
        warning = estimate.metr_warning.message if estimate.metr_warning is not None else None
        return cls(
            name=name,
            tier=estimate.sizing.tier.value,
            agent=agent,
            base_pert_optimistic_minutes=estimate.sizing.baseline_optimistic,
            base_pert_most_likely_minutes=estimate.sizing.baseline_most_likely,
            base_pert_pessimistic_minutes=estimate.sizing.baseline_pessimistic,
            modifier_spec_clarity=estimate.modifiers.spec_clarity,
            modifier_warm_context=estimate.modifiers.warm_context,
            modifier_agent_fit=estimate.modifiers.agent_fit,
            modifier_combined=estimate.modifiers.combined,
            effective_duration_minutes=estimate.pert.expected,
            human_equivalent_minutes=estimate.human_equivalent_minutes,
            review_overhead_minutes=estimate.review_minutes,
            metr_warning=warning,
        )


@dataclass(frozen=True)
class ReportWave:
    """One scheduling wave in the report."""

    number: int
    tasks: tuple[str, ...]
    duration_minutes: float
    agent_assignments: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class ReportTimeline:
    """Top-level timeline summary metrics."""

    best_case_minutes: float
    expected_case_minutes: float
    worst_case_minutes: float
    human_equivalent_minutes: float

    @property
    def compression_ratio(self) -> float:
        """Return human/agent ratio. Returns 0 when expected time is 0."""
        if self.expected_case_minutes <= 0:
            return 0.0
        return self.human_equivalent_minutes / self.expected_case_minutes


@dataclass(frozen=True)
class ReportAgentLoad:
    """Agent-level load and cost totals."""

    agent: str
    task_count: int
    total_work_minutes: float
    estimated_cost: float


@dataclass(frozen=True)
class EstimationReport:
    """Renderer input bundle for a full estimate report."""

    tasks: tuple[ReportTask, ...]
    waves: tuple[ReportWave, ...]
    timeline: ReportTimeline
    agent_load: tuple[ReportAgentLoad, ...]
    critical_path: tuple[str, ...]
    title: str = "Agent Estimate Report"

    @property
    def review_overhead_minutes(self) -> float:
        """Sum additive review overhead across all tasks."""
        return sum(task.review_overhead_minutes for task in self.tasks)
