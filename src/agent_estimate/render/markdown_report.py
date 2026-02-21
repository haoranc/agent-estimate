"""Markdown report renderer."""

from __future__ import annotations

from agent_estimate.render.report_models import EstimationReport


def render_markdown_report(report: EstimationReport) -> str:
    """Render an estimation report as GitHub-compatible Markdown."""
    lines: list[str] = [
        f"# {report.title}",
        "",
    ]
    lines.extend(_render_task_table(report))
    lines.extend([""])
    lines.extend(_render_wave_table(report))
    lines.extend([""])
    lines.extend(_render_timeline_summary(report))
    lines.extend([""])
    lines.extend(_render_review_overhead(report))
    lines.extend([""])
    lines.extend(_render_agent_load_table(report))
    lines.extend([""])
    lines.extend(_render_critical_path(report))
    lines.extend([""])
    lines.extend(_render_metr_warnings(report))
    lines.append("")
    return "\n".join(lines)


def _render_task_table(report: EstimationReport) -> list[str]:
    critical_tasks = set(report.critical_path)
    lines = [
        "## Per-Task Estimates",
        "",
        "| Task | Tier | Agent | Base PERT (O/M/P) | Modifiers | Effective Duration | Human Equivalent |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in report.tasks:
        task_name = _escape_cell(task.name)
        if task.name in critical_tasks:
            task_name = f"**{task_name}**"
        base_pert = (
            f"{_format_minutes(task.base_pert_optimistic_minutes)} / "
            f"{_format_minutes(task.base_pert_most_likely_minutes)} / "
            f"{_format_minutes(task.base_pert_pessimistic_minutes)} "
            f"(E={_format_minutes(task.base_pert_expected_minutes)})"
        )
        warm_str = f"warm {task.modifier_warm_context:.2f}"
        if task.warm_context_detail:
            warm_str += f" (auto: {task.warm_context_detail})"
        modifiers = (
            f"spec {task.modifier_spec_clarity:.2f} x "
            f"{warm_str} x "
            f"fit {task.modifier_agent_fit:.2f} = {task.modifier_combined:.2f}"
        )
        human = (
            _format_minutes(task.human_equivalent_minutes)
            if task.human_equivalent_minutes is not None
            else "N/A"
        )
        lines.append(
            f"| {task_name} | {task.tier} | {_escape_cell(task.agent)} | {base_pert} | "
            f"{modifiers} | {_format_minutes(task.effective_duration_minutes)} | {human} |"
        )
    return lines


def _render_wave_table(report: EstimationReport) -> list[str]:
    lines = [
        "## Wave Plan",
        "",
        "| Wave | Tasks | Duration | Agent Assignments (amortized review) |",
        "| --- | --- | --- | --- |",
    ]
    for wave in report.waves:
        tasks = ", ".join(_escape_cell(task_name) for task_name in wave.tasks) or "N/A"
        assignments: list[str] = []
        for agent in sorted(wave.agent_assignments):
            assigned_tasks = ", ".join(_escape_cell(task) for task in wave.agent_assignments[agent])
            review_m = wave.agent_review_minutes.get(agent, 0.0)
            review_note = f" +{_format_minutes(review_m)} review" if review_m > 0 else ""
            assignments.append(f"{_escape_cell(agent)}: {assigned_tasks or 'none'}{review_note}")
        assignment_text = "; ".join(assignments) if assignments else "N/A"
        lines.append(
            f"| {wave.number} | {tasks} | {_format_minutes(wave.duration_minutes)} | "
            f"{assignment_text} |"
        )
    return lines


def _render_timeline_summary(report: EstimationReport) -> list[str]:
    timeline = report.timeline
    return [
        "## Timeline Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Best case | {_format_minutes(timeline.best_case_minutes)} |",
        f"| Expected case | {_format_minutes(timeline.expected_case_minutes)} |",
        f"| Worst case | {_format_minutes(timeline.worst_case_minutes)} |",
        f"| Human-speed equivalent | {_format_minutes(timeline.human_equivalent_minutes)} |",
        f"| Compression ratio | {timeline.compression_ratio:.2f}x |",
        f"| Review overhead (per-task, pre-amortization) | {_format_minutes(report.review_overhead_minutes)} |",
    ]


def _render_review_overhead(report: EstimationReport) -> list[str]:
    lines = [
        "## Review Overhead",
        "",
        "Review is amortized per agent per wave: one review cycle covers all PRs from that",
        "agent in the wave.  Per-task values below are the naive (pre-amortization) figures.",
        "",
        "| Task | Review Overhead |",
        "| --- | --- |",
    ]
    for task in report.tasks:
        lines.append(f"| {_escape_cell(task.name)} | {_format_minutes(task.review_overhead_minutes)} |")
    lines.append(f"| **Total (naive)** | **{_format_minutes(report.review_overhead_minutes)}** |")
    return lines


def _render_agent_load_table(report: EstimationReport) -> list[str]:
    lines = [
        "## Agent Load Summary",
        "",
        "| Agent | Task Count | Total Work | Estimated Cost |",
        "| --- | --- | --- | --- |",
    ]
    for load in report.agent_load:
        lines.append(
            f"| {_escape_cell(load.agent)} | {load.task_count} | "
            f"{_format_minutes(load.total_work_minutes)} | ${load.estimated_cost:.2f} |"
        )
    return lines


def _render_critical_path(report: EstimationReport) -> list[str]:
    lines = ["## Critical Path", ""]
    if not report.critical_path:
        lines.append("No critical path provided.")
        return lines
    path = " -> ".join(f"**{_escape_cell(task_name)}**" for task_name in report.critical_path)
    lines.append(path)
    return lines


def _render_metr_warnings(report: EstimationReport) -> list[str]:
    lines = ["## METR Warnings", ""]
    warnings = [(task.name, task.metr_warning) for task in report.tasks if task.metr_warning]
    if not warnings:
        lines.append("No METR threshold warnings.")
        return lines
    for task_name, warning in warnings:
        lines.append(f"- **{_escape_cell(task_name)}**: {_escape_cell(str(warning))}")
    return lines


def _format_minutes(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - int(rounded)) < 1e-9:
        return f"{int(rounded)}m"
    return f"{rounded:.1f}m"


def _escape_cell(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return normalized.replace("|", "\\|")
