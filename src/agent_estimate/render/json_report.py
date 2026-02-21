"""JSON report renderer."""

from __future__ import annotations

import json
from typing import Any

from agent_estimate.render.report_models import EstimationReport, ReportWave


def render_json_report(report: EstimationReport) -> str:
    """Render an estimation report as canonical JSON."""
    payload = _build_payload(report)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _build_payload(report: EstimationReport) -> dict[str, Any]:
    critical_tasks = set(report.critical_path)
    warnings = [
        {
            "task": task.name,
            "warning": task.metr_warning,
        }
        for task in report.tasks
        if task.metr_warning is not None
    ]

    return {
        "title": report.title,
        "tasks": [
            {
                "name": task.name,
                "tier": task.tier,
                "agent": task.agent,
                "base_pert": {
                    "optimistic_minutes": task.base_pert_optimistic_minutes,
                    "most_likely_minutes": task.base_pert_most_likely_minutes,
                    "pessimistic_minutes": task.base_pert_pessimistic_minutes,
                    "expected_minutes": task.base_pert_expected_minutes,
                },
                "modifiers": {
                    "spec_clarity": task.modifier_spec_clarity,
                    "warm_context": task.modifier_warm_context,
                    "agent_fit": task.modifier_agent_fit,
                    "combined": task.modifier_combined,
                    "raw_combined": task.modifier_raw_combined,
                    "clamped": task.modifier_clamped,
                },
                "estimation_category": task.estimation_category.value if task.estimation_category is not None else None,
                "effective_duration_minutes": task.effective_duration_minutes,
                "human_equivalent_minutes": task.human_equivalent_minutes,
                "review_overhead_minutes": task.review_overhead_minutes,
                "metr_warning": task.metr_warning,
                "is_critical_path": task.name in critical_tasks,
            }
            for task in report.tasks
        ],
        "waves": [_wave_payload(wave) for wave in sorted(report.waves, key=lambda wave: wave.number)],
        "timeline": {
            "best_case_minutes": report.timeline.best_case_minutes,
            "expected_case_minutes": report.timeline.expected_case_minutes,
            "worst_case_minutes": report.timeline.worst_case_minutes,
            "human_equivalent_minutes": report.timeline.human_equivalent_minutes,
            "compression_ratio": report.timeline.compression_ratio,
            "review_overhead_minutes": report.review_overhead_minutes,
        },
        "agent_load": [
            {
                "agent": load.agent,
                "task_count": load.task_count,
                "total_work_minutes": load.total_work_minutes,
                "estimated_cost": load.estimated_cost,
            }
            for load in sorted(report.agent_load, key=lambda load: load.agent)
        ],
        "critical_path": list(report.critical_path),
        "metr_warnings": warnings,
    }


def _wave_payload(wave: ReportWave) -> dict[str, Any]:
    assignments = {
        agent: sorted(tasks)
        for agent, tasks in sorted(wave.agent_assignments.items(), key=lambda item: item[0])
    }
    return {
        "number": wave.number,
        "tasks": sorted(wave.tasks),
        "duration_minutes": wave.duration_minutes,
        "agent_assignments": assignments,
        "agent_review_minutes": dict(sorted(wave.agent_review_minutes.items())),
    }
