"""Estimation pipeline — orchestrates core engines into a report."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import NoReturn, Sequence

from agent_estimate.core import (
    EstimationCategory,
    EstimationConfig,
    ReviewMode,
    TaskEstimate,
    TaskNode,
    WavePlan,
    auto_correct_tier,
    classify_task,
    build_modifier_set,
    check_metr_threshold,
    compute_human_equivalent,
    detect_estimation_category,
    estimate_brainstorm,
    estimate_config_sre,
    estimate_documentation,
    estimate_research,
    estimate_task,
    load_metr_thresholds,
    plan_waves,
)
from agent_estimate.render import (
    EstimationReport,
    ReportAgentLoad,
    ReportTask,
    ReportTimeline,
    ReportWave,
)

logger = logging.getLogger("agent_estimate")

_MINUTES_PER_TURN = 5.0


def _error(message: str, exit_code: int) -> NoReturn:
    """Print error to stderr and exit."""
    import typer

    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=exit_code)


def _truncate_name(desc: str, max_len: int = 60) -> str:
    """Truncate a task description for table readability."""
    desc = desc.strip().split("\n", 1)[0]
    if len(desc) <= max_len:
        return desc
    return desc[: max_len - 1] + "\u2026"


def _estimate_by_category(
    category: EstimationCategory,
    desc: str,
    modifiers,
    *,
    review_mode: ReviewMode,
    model_key: str,
    thresholds,
    fallback: float,
    agent_name: str | None,
    sizing,
    auto_tier: bool,
    estimated_tests: int | None,
    estimated_lines: int | None,
    num_concerns: int | None,
) -> tuple[TaskEstimate, list[str]]:
    """Route estimation to the correct model based on category.

    Returns (estimate, tier_warnings).
    """
    task_tier_warnings: list[str] = []

    if category == EstimationCategory.BRAINSTORM:
        est = estimate_brainstorm(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
        )
        return est, task_tier_warnings

    if category == EstimationCategory.RESEARCH:
        est = estimate_research(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
        )
        return est, task_tier_warnings

    if category == EstimationCategory.CONFIG_SRE:
        est = estimate_config_sre(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
        )
        return est, task_tier_warnings

    if category == EstimationCategory.DOCUMENTATION:
        est = estimate_documentation(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
        )
        return est, task_tier_warnings

    # Default: CODING — PERT tier model with auto-correction
    if auto_tier:
        correction = auto_correct_tier(
            sizing,
            estimated_tests=estimated_tests,
            estimated_lines=estimated_lines,
            num_concerns=num_concerns,
        )
        if correction.warnings:
            for w in correction.warnings:
                logger.warning("auto-tier: %s", w)
                task_tier_warnings.append(w)
        sizing = correction.sizing

    # First pass — get total_expected_minutes
    est = estimate_task(
        sizing,
        modifiers,
        review_mode=review_mode,
        model_key=model_key,
        thresholds=thresholds,
        fallback_threshold=fallback,
        agent_name=agent_name,
    )
    # Compute human equivalent and re-estimate with it filled in
    human_eq = compute_human_equivalent(est.total_expected_minutes, sizing.task_type)
    est = estimate_task(
        sizing,
        modifiers,
        review_mode=review_mode,
        model_key=model_key,
        thresholds=thresholds,
        fallback_threshold=fallback,
        agent_name=agent_name,
        human_equivalent_minutes=human_eq,
    )
    # Attach category to the estimate
    est = replace(est, estimation_category=EstimationCategory.CODING)
    return est, task_tier_warnings


def run_estimate_pipeline(
    descriptions: Sequence[str],
    config: EstimationConfig,
    review_mode: ReviewMode = ReviewMode.STANDARD,
    title: str = "Agent Estimate Report",
    spec_clarity: float = 1.0,
    warm_context: float = 1.0,
    agent_fit: float = 1.0,
    warm_context_detail: str | None = None,
    auto_tier: bool = True,
    estimated_tests: int | None = None,
    estimated_lines: int | None = None,
    num_concerns: int | None = None,
    task_category: EstimationCategory | None = None,
) -> EstimationReport:
    """Run the full estimation pipeline and produce a report."""
    if not config.agents:
        _error("config.agents must be non-empty", 2)

    thresholds = load_metr_thresholds()
    # Use first agent's tier for initial estimation pass; METR warnings are
    # corrected per-task after wave planning assigns each task to an agent.
    initial_model_key = config.agents[0].model_tier
    initial_agent_name = config.agents[0].name
    fallback = config.settings.metr_fallback_threshold

    names: list[str] = []
    estimates: list[TaskEstimate] = []
    tier_warnings: list[list[str]] = []
    modifiers = build_modifier_set(
        spec_clarity=spec_clarity,
        warm_context=warm_context,
        agent_fit=agent_fit,
    )

    for desc in descriptions:
        name = _truncate_name(desc)
        logger.debug("Estimating task: %s", name)

        # Determine the estimation category for this task
        if task_category is not None:
            category = task_category
        else:
            category = detect_estimation_category(desc)

        # classify_task runs the PERT coding model; skip it for non-coding categories
        sizing = classify_task(desc) if category == EstimationCategory.CODING else None

        est, task_tier_warnings = _estimate_by_category(
            category,
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=initial_model_key,
            thresholds=thresholds,
            fallback=fallback,
            agent_name=initial_agent_name,
            sizing=sizing,
            auto_tier=auto_tier,
            estimated_tests=estimated_tests,
            estimated_lines=estimated_lines,
            num_concerns=num_concerns,
        )
        tier_warnings.append(task_tier_warnings)

        names.append(name)
        estimates.append(est)

    # Build TaskNodes for wave planning (friction applied here)
    friction = config.settings.friction_multiplier
    task_nodes = [
        TaskNode(
            task_id=str(i),
            duration_minutes=est.total_expected_minutes * friction,
        )
        for i, est in enumerate(estimates)
    ]

    wave_plan = plan_waves(
        task_nodes,
        config.agents,
        inter_wave_overhead_hours=config.settings.inter_wave_overhead,
    )

    return _build_report(
        names, estimates, wave_plan, config, title, thresholds, fallback,
        warm_context_detail=warm_context_detail,
        tier_warnings=tier_warnings,
    )


def _build_report(
    names: list[str],
    estimates: list[TaskEstimate],
    wave_plan: WavePlan,
    config: EstimationConfig,
    title: str,
    thresholds: dict[str, float] | None = None,
    fallback: float = 40.0,
    warm_context_detail: str | None = None,
    tier_warnings: list[list[str]] | None = None,
) -> EstimationReport:
    """Map wave planner outputs back to report models."""
    # Build assignment map: task_id -> agent_name
    assignment_map: dict[str, str] = {}
    for wave in wave_plan.waves:
        for a in wave.assignments:
            assignment_map[a.task_id] = a.agent_name

    default_agent = config.agents[0].name

    # Build agent model tier map: agent_name -> model_tier
    agent_model_tier: dict[str, str] = {a.name: a.model_tier for a in config.agents}
    default_tier = config.agents[0].model_tier

    # Report tasks — re-evaluate METR warnings using the assigned agent's model tier
    report_task_list: list[ReportTask] = []
    for i, est in enumerate(estimates):
        assigned_agent = assignment_map.get(str(i), default_agent)
        model_tier = agent_model_tier.get(assigned_agent, default_tier)

        # Re-check METR threshold with the assigned agent's model tier
        corrected_warning = check_metr_threshold(
            model_tier,
            est.total_expected_minutes,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=assigned_agent,
        )
        warning_message = corrected_warning.message if corrected_warning is not None else None

        task_tier_warnings = tier_warnings[i] if tier_warnings else []
        report_task_list.append(
            ReportTask(
                name=names[i],
                tier=est.sizing.tier.value,
                agent=assigned_agent,
                base_pert_optimistic_minutes=est.sizing.baseline_optimistic,
                base_pert_most_likely_minutes=est.sizing.baseline_most_likely,
                base_pert_pessimistic_minutes=est.sizing.baseline_pessimistic,
                modifier_spec_clarity=est.modifiers.spec_clarity,
                modifier_warm_context=est.modifiers.warm_context,
                modifier_agent_fit=est.modifiers.agent_fit,
                modifier_combined=est.modifiers.combined,
                effective_duration_minutes=est.pert.expected,
                human_equivalent_minutes=est.human_equivalent_minutes,
                review_overhead_minutes=est.review_minutes,
                metr_warning=warning_message,
                warm_context_detail=warm_context_detail,
                tier_correction_warnings=tuple(task_tier_warnings),
                estimation_category=est.estimation_category,
            )
        )
    report_tasks = tuple(report_task_list)

    # Report waves
    report_waves = tuple(
        ReportWave(
            number=wave.wave_number,
            tasks=tuple(names[int(a.task_id)] for a in wave.assignments),
            duration_minutes=wave.end_minutes - wave.start_minutes,
            agent_assignments={
                agent_name: tuple(
                    names[int(aa.task_id)]
                    for aa in wave.assignments
                    if aa.agent_name == agent_name
                )
                for agent_name in {a.agent_name for a in wave.assignments}
            },
        )
        for wave in wave_plan.waves
    )

    # Timeline — scale best/worst by parallel efficiency ratio
    # pert.optimistic/pessimistic already have modifiers applied (via estimate_task)
    total_best = sum(e.pert.optimistic + e.review_minutes for e in estimates)
    total_expected = sum(e.total_expected_minutes for e in estimates)
    total_worst = sum(e.pert.pessimistic + e.review_minutes for e in estimates)
    total_human = sum(
        e.human_equivalent_minutes
        for e in estimates
        if e.human_equivalent_minutes is not None
    )

    if total_expected > 0:
        ratio = wave_plan.total_wall_clock_minutes / total_expected
    else:
        ratio = 1.0

    timeline = ReportTimeline(
        best_case_minutes=total_best * ratio,
        expected_case_minutes=wave_plan.total_wall_clock_minutes,
        worst_case_minutes=total_worst * ratio,
        human_equivalent_minutes=total_human,
    )

    # Agent load — initialize all agents to 0
    agent_work: dict[str, float] = {a.name: 0.0 for a in config.agents}
    agent_tasks: dict[str, int] = {a.name: 0 for a in config.agents}
    cost_per_turn: dict[str, float] = {
        a.name: a.cost_per_turn for a in config.agents
    }

    for wave in wave_plan.waves:
        for a in wave.assignments:
            if a.agent_name in agent_work:
                agent_work[a.agent_name] += a.duration_minutes
                agent_tasks[a.agent_name] += 1

    report_agent_load = tuple(
        ReportAgentLoad(
            agent=name,
            task_count=agent_tasks[name],
            total_work_minutes=agent_work[name],
            estimated_cost=agent_work[name] / _MINUTES_PER_TURN * cost_per_turn[name],
        )
        for name in agent_work
    )

    # Critical path — map task_ids to names
    critical_path = tuple(
        names[int(tid)] for tid in wave_plan.critical_path
    )

    return EstimationReport(
        tasks=report_tasks,
        waves=report_waves,
        timeline=timeline,
        agent_load=report_agent_load,
        critical_path=critical_path,
        title=title,
    )
