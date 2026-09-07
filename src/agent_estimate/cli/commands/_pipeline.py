"""Estimation pipeline — orchestrates core engines into a report."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from numbers import Real
from typing import NoReturn

from agent_estimate.core import (
    EstimationCategory,
    EstimationConfig,
    ReviewMode,
    TaskEstimate,
    TaskNode,
    WavePlan,
    auto_correct_tier,
    build_modifier_set,
    check_metr_threshold,
    classify_task,
    compute_human_equivalent,
    detect_estimation_category,
    estimate_app_dev,
    estimate_brainstorm,
    estimate_config_sre,
    estimate_documentation,
    estimate_frontend,
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

    if auto_tier:
        correction = auto_correct_tier(
            sizing,
            estimated_tests=estimated_tests,
            estimated_lines=estimated_lines,
            num_concerns=num_concerns,
        )
        if correction.warnings:
            for warning in correction.warnings:
                logger.warning("auto-tier: %s", warning)
                task_tier_warnings.append(warning)
        sizing = correction.sizing

    if category == EstimationCategory.BRAINSTORM:
        est = estimate_brainstorm(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
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
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
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
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
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
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
        return est, task_tier_warnings

    if category == EstimationCategory.FRONTEND:
        est = estimate_frontend(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
        return est, task_tier_warnings

    if category == EstimationCategory.APP_DEV:
        est = estimate_app_dev(
            desc,
            modifiers,
            review_mode=review_mode,
            model_key=model_key,
            thresholds=thresholds,
            fallback_threshold=fallback,
            agent_name=agent_name,
            size_hint=sizing,
        )
        human_eq = compute_human_equivalent(est.pert.expected, est.sizing.task_type)
        est = replace(est, human_equivalent_minutes=human_eq)
        return est, task_tier_warnings

    # Default: CODING — PERT tier model
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
    human_eq = compute_human_equivalent(est.pert.expected, sizing.task_type)
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
    required_capabilities: Sequence[str] = (),
) -> EstimationReport:
    """Run the full estimation pipeline and produce a report."""
    if not config.agents:
        _error("config.agents must be non-empty", 2)

    thresholds = load_metr_thresholds()
    # Use first agent's tier for initial estimation pass; reliability warnings are
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

        # One size classifier feeds every category; category models scale their
        # own baselines instead of collapsing all non-coding work to a fixed S.
        sizing = classify_task(desc)

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

    # Build TaskNodes for wave planning (friction applied to work only).
    # review_minutes is kept separate so the wave planner can amortize it
    # across same-agent tasks in each wave (batch review amortization).
    friction = config.settings.friction_multiplier
    task_nodes = [
        TaskNode(
            task_id=str(i),
            duration_minutes=est.pert.expected * friction,
            # review_minutes is flat additive overhead, not scaled by friction
            review_minutes=est.review_minutes,
            required_capabilities=tuple(required_capabilities),
        )
        for i, est in enumerate(estimates)
    ]

    wave_plan = plan_waves(
        task_nodes,
        config.agents,
        inter_wave_overhead_hours=config.settings.inter_wave_overhead,
    )
    estimates, wave_plan = _adjust_assigned_estimates(estimates, task_nodes, wave_plan, config)

    return _build_report(
        names, estimates, wave_plan, config, title, thresholds, fallback,
        warm_context_detail=warm_context_detail,
        tier_warnings=tier_warnings,
    )


def _adjust_assigned_estimates(
    estimates: list[TaskEstimate],
    task_nodes: list[TaskNode],
    plan: WavePlan,
    config: EstimationConfig,
) -> tuple[list[TaskEstimate], WavePlan]:
    """Apply each selected profile once, then retime the fixed assignment.

    The hook's result determines one scalar for the task's entire PERT range.
    Review and human-equivalent work are unchanged. No scheduling fixpoint is run.
    """
    profiles = {agent.name: agent for agent in config.agents}
    assigned = {a.task_id: a.agent_name for wave in plan.waves for a in wave.assignments}
    factors: dict[str, float] = {}
    adjusted_estimates: list[TaskEstimate] = []
    for node, estimate in zip(task_nodes, estimates, strict=True):
        agent = profiles[assigned[node.task_id]]
        minutes = estimate.pert.expected
        try:
            adjusted = agent.adjust_estimate(minutes)
        except Exception as exc:
            raise ValueError(f"Agent {agent.name!r} adjust_estimate failed: {exc}") from exc
        try:
            finite = math.isfinite(adjusted) if isinstance(adjusted, Real) else False
        except OverflowError:
            finite = False
        if (
            isinstance(adjusted, bool)
            or not isinstance(adjusted, Real)
            or not finite
            or (minutes > 0 and adjusted <= 0)
            or (minutes == 0 and adjusted != 0)
        ):
            raise ValueError(
                f"Agent {agent.name!r} adjust_estimate must return finite positive work "
                "(or zero for zero work)."
            )
        factor = float(adjusted) / minutes if minutes else 1.0
        if factor <= 0:
            raise ValueError(f"Agent {agent.name!r} adjustment underflowed the estimate.")
        pert = replace(
            estimate.pert,
            **{key: getattr(estimate.pert, key) * factor for key in (
                "optimistic", "most_likely", "pessimistic", "expected", "sigma",
            )},
        )
        if not all(math.isfinite(value) for value in (
            factor, pert.optimistic, pert.most_likely, pert.pessimistic, pert.expected,
            pert.sigma, pert.expected + estimate.review_minutes,
        )):
            raise ValueError(f"Agent {agent.name!r} adjustment overflowed the estimate.")
        factors[node.task_id] = factor
        adjusted_estimates.append(replace(
            estimate, pert=pert, total_expected_minutes=pert.expected + estimate.review_minutes,
            estimate_factor=factor, pre_adjustment_minutes=minutes,
        ))

    if all(factor == 1.0 for factor in factors.values()):
        return estimates, plan

    # Retain friction and the planner's co-dispatch reduction in each assignment.
    waves = []
    busy = {agent.name: 0.0 for agent in config.agents}
    previous_end = 0.0
    new_end = 0.0
    for wave in plan.waves:
        assignments = tuple(replace(
            a, duration_minutes=a.duration_minutes * factors[a.task_id],
        ) for a in wave.assignments)
        slot_work: dict[tuple[str, int], float] = defaultdict(float)
        for assignment in assignments:
            slot_work[(assignment.agent_name, assignment.slot_index)] += assignment.duration_minutes
            busy[assignment.agent_name] += assignment.duration_minutes
        makespan = max((
            work + wave.agent_review_minutes.get(name, 0.0)
            for (name, _slot), work in slot_work.items()
        ), default=0.0)
        start = new_end + (wave.start_minutes - previous_end)
        new_end = start + makespan
        waves.append(replace(wave, assignments=assignments, start_minutes=start, end_minutes=new_end))
        previous_end = wave.end_minutes

    nodes = {node.task_id: node for node in task_nodes}
    work = {node.task_id: node.duration_minutes * factors[node.task_id] for node in task_nodes}
    distances: dict[str, float] = {}
    predecessors: dict[str, str | None] = {}
    # Existing waves supply dependency order; use adjusted pre-co-dispatch work,
    # matching the planner's critical-path and sequential-baseline definitions.
    for wave in waves:
        for assignment in wave.assignments:
            task_id = assignment.task_id
            deps = nodes[task_id].dependencies
            predecessor = max(deps, key=distances.__getitem__) if deps else None
            predecessors[task_id] = predecessor
            distances[task_id] = work[task_id] + (distances[predecessor] if predecessor else 0.0)
    end = max(nodes, key=distances.__getitem__)
    critical_minutes = distances[end]
    path = []
    cursor: str | None = end
    while cursor is not None:
        path.append(cursor)
        cursor = predecessors[cursor]
    sequential = sum(work.values()) + sum(
        sum(wave.agent_review_minutes.values()) for wave in waves
    )
    if not all(math.isfinite(value) for value in (
        new_end, sequential, *work.values(), *busy.values(), *distances.values(),
    )):
        raise ValueError("Profile adjustment overflowed the wave plan.")
    utilization = {
        name: value / new_end / profiles[name].parallelism if new_end else 0.0
        for name, value in sorted(busy.items())
    }
    slots = sum(agent.parallelism for agent in config.agents)
    return adjusted_estimates, replace(
        plan, waves=tuple(waves), critical_path=tuple(reversed(path)),
        critical_path_minutes=critical_minutes, agent_utilization=utilization,
        parallel_efficiency=min(1.0, sequential / new_end / slots) if new_end else 0.0,
        total_wall_clock_minutes=new_end, total_sequential_minutes=sequential,
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

    # Re-evaluate reliability warnings using the assigned agent's model tier.
    report_task_list: list[ReportTask] = []
    for i, est in enumerate(estimates):
        assigned_agent = assignment_map.get(str(i), default_agent)
        model_tier = agent_model_tier.get(assigned_agent, default_tier)

        # Re-check the policy with the assigned agent's model tier and the
        # same frictioned work duration the wave planner schedules.
        metr_minutes = est.pert.expected * config.settings.friction_multiplier
        corrected_warning = check_metr_threshold(
            model_tier,
            metr_minutes,
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
                modifier_raw_combined=est.modifiers.raw_combined,
                modifier_clamped=est.modifiers.clamped,
                effective_duration_minutes=est.pert.expected,
                human_equivalent_minutes=est.human_equivalent_minutes,
                review_overhead_minutes=est.review_minutes,
                metr_warning=warning_message,
                warm_context_detail=warm_context_detail,
                tier_correction_warnings=tuple(task_tier_warnings),
                estimation_category=est.estimation_category,
                estimate_factor=est.estimate_factor,
                pre_adjustment_minutes=est.pre_adjustment_minutes,
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
            agent_review_minutes=dict(wave.agent_review_minutes),
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
    if not all(math.isfinite(value) for value in (
        timeline.best_case_minutes, timeline.expected_case_minutes,
        timeline.worst_case_minutes, timeline.human_equivalent_minutes,
        timeline.compression_ratio,
    )):
        raise ValueError("Estimation overflowed the report timeline.")

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
    if not all(math.isfinite(load.heuristic_cost) for load in report_agent_load):
        raise ValueError("Estimation overflowed the heuristic cost.")

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
        registry_version=getattr(thresholds, "registry_version", "unversioned"),
        basis="expected-wall",
        source="bundled task-category priors; n=0 calibration observations applied",
        # No dated duration calibration snapshot is applied by this pipeline.
        as_of=None,
    )
