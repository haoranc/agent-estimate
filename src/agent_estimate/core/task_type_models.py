"""Estimation models for non-coding task categories.

Non-coding tasks have fundamentally different time profiles from coding tasks.
Evidence: 33 coding dispatches at 0.85x mean ratio (well-calibrated) vs
6 brainstorm dispatches at 0.08x (10-20x overestimate when using PERT coding model).

Each category provides a flat or range-based estimate rather than PERT tiers.
"""

from __future__ import annotations

import re

from agent_estimate.core.models import (
    EstimationCategory,
    ModifierSet,
    ReviewMode,
    SizeTier,
    SizingResult,
    TaskEstimate,
    TaskType,
)
from agent_estimate.core.modifiers import compute_review_overhead
from agent_estimate.core.pert import check_metr_threshold, compute_pert

# ---------------------------------------------------------------------------
# Auto-detection patterns for EstimationCategory
# ---------------------------------------------------------------------------

_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], EstimationCategory]] = [
    # Brainstorm — ideation, design, discussion
    (
        re.compile(
            r"\b(brainstorm|ideate|explore ideas?|design session|whiteboard|discuss|"
            r"spike|discovery|kickoff|alignment|sync)\b",
            re.I,
        ),
        EstimationCategory.BRAINSTORM,
    ),
    # Research — investigation, analysis, evaluation
    (
        re.compile(
            r"\b(research|investigate|analyze|analyse|survey|evaluate|"
            r"feasibility|benchmarks?|compare|assessment|audit)\b",
            re.I,
        ),
        EstimationCategory.RESEARCH,
    ),
    # Config / SRE — infrastructure, deployment, ops
    (
        re.compile(
            r"\b(config(?:ure|uration)?|deploy(?:ment)?|infra(?:structure)?|"
            r"sre|devops|terraform|helm|ansible|k8s|kubernetes|"
            r"ci/?cd|pipeline|monitoring|alerting|oncall|runbook|"
            r"env(?:ironment)? var(?:iable)?s?|secret(?:s| management)?)\b",
            re.I,
        ),
        EstimationCategory.CONFIG_SRE,
    ),
    # Documentation — writing, docs, readme
    (
        re.compile(
            r"\b(doc(?:umentation|s)?|readme|write up|write-up|changelog|"
            r"api docs?|wiki|confluence|technical writing|specification)\b",
            re.I,
        ),
        EstimationCategory.DOCUMENTATION,
    ),
]

# ---------------------------------------------------------------------------
# Flat-model baselines (O, M, P) in minutes per category
# ---------------------------------------------------------------------------

# Brainstorm: independent task (~10m), synthesis/follow-up (~5m)
# We use a symmetric PERT triple, keeping spread tight.
_BRAINSTORM_BASELINES = (5.0, 10.0, 15.0)

# Research: time-boxed 15-45m depending on depth
_RESEARCH_BASELINES_SHALLOW = (10.0, 20.0, 30.0)
_RESEARCH_BASELINES_DEEP = (25.0, 35.0, 50.0)

# Config/SRE: flat + verification overhead
_CONFIG_SRE_BASELINES = (10.0, 20.0, 35.0)

# Documentation: line-count based — lower floor than coding
_DOCUMENTATION_BASELINES = (10.0, 25.0, 45.0)

# Depth keywords that push research to the "deep" band
_RESEARCH_DEEP_PATTERNS = re.compile(
    r"\b(deep|thorough|comprehensive|in[-\s]?depth|extensive|detailed|"
    r"literature review|systematic|full|complete)\b",
    re.I,
)


def detect_estimation_category(text: str) -> EstimationCategory:
    """Infer EstimationCategory from task title / description text.

    Returns CODING as the default when no non-coding signals are found.
    """
    if not text or not text.strip():
        return EstimationCategory.CODING
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return EstimationCategory.CODING


def _make_non_coding_sizing(
    o: float, m: float, p: float, label: str
) -> SizingResult:
    """Build a synthetic SizingResult for non-coding tasks."""
    return SizingResult(
        tier=SizeTier.S,  # tier is not meaningful for non-coding; use S as placeholder
        baseline_optimistic=o,
        baseline_most_likely=m,
        baseline_pessimistic=p,
        task_type=TaskType.UNKNOWN,
        signals=(label,),
    )


def estimate_brainstorm(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
) -> TaskEstimate:
    """Estimate a brainstorm / ideation task.

    Uses a flat ~10m model. Modifiers still apply so warm context and agent fit
    can reduce time for follow-up sessions.
    """
    _ = description  # reserved for future heuristics

    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _BRAINSTORM_BASELINES
    sizing = _make_non_coding_sizing(o, m, p, "brainstorm-flat-model")

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        total,
        thresholds=thresholds,
        fallback_threshold=fallback_threshold,
        agent_name=agent_name,
    )

    return TaskEstimate(
        sizing=sizing,
        pert=pert,
        modifiers=modifiers,
        review_minutes=review_minutes,
        total_expected_minutes=total,
        human_equivalent_minutes=human_equivalent_minutes,
        metr_warning=metr_warning,
        estimation_category=EstimationCategory.BRAINSTORM,
    )


def estimate_research(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
) -> TaskEstimate:
    """Estimate a research / investigation task.

    Uses a time-boxed model: 15-30m for shallow, 25-50m for deep research.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    if _RESEARCH_DEEP_PATTERNS.search(description or ""):
        o, m, p = _RESEARCH_BASELINES_DEEP
        label = "research-deep-model"
    else:
        o, m, p = _RESEARCH_BASELINES_SHALLOW
        label = "research-shallow-model"

    sizing = _make_non_coding_sizing(o, m, p, label)

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        total,
        thresholds=thresholds,
        fallback_threshold=fallback_threshold,
        agent_name=agent_name,
    )

    return TaskEstimate(
        sizing=sizing,
        pert=pert,
        modifiers=modifiers,
        review_minutes=review_minutes,
        total_expected_minutes=total,
        human_equivalent_minutes=human_equivalent_minutes,
        metr_warning=metr_warning,
        estimation_category=EstimationCategory.RESEARCH,
    )


def estimate_config_sre(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
) -> TaskEstimate:
    """Estimate a config / SRE / infrastructure task.

    Uses a flat + verification model: ~15-30m.
    """
    _ = description  # reserved for future heuristics

    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _CONFIG_SRE_BASELINES
    sizing = _make_non_coding_sizing(o, m, p, "config-sre-flat-model")

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        total,
        thresholds=thresholds,
        fallback_threshold=fallback_threshold,
        agent_name=agent_name,
    )

    return TaskEstimate(
        sizing=sizing,
        pert=pert,
        modifiers=modifiers,
        review_minutes=review_minutes,
        total_expected_minutes=total,
        human_equivalent_minutes=human_equivalent_minutes,
        metr_warning=metr_warning,
        estimation_category=EstimationCategory.CONFIG_SRE,
    )


def estimate_documentation(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
) -> TaskEstimate:
    """Estimate a documentation task.

    Uses a line-count-based model similar to coding but with a lower floor: 10-45m.
    """
    _ = description  # reserved for future heuristics

    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _DOCUMENTATION_BASELINES
    sizing = _make_non_coding_sizing(o, m, p, "documentation-model")

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        total,
        thresholds=thresholds,
        fallback_threshold=fallback_threshold,
        agent_name=agent_name,
    )

    return TaskEstimate(
        sizing=sizing,
        pert=pert,
        modifiers=modifiers,
        review_minutes=review_minutes,
        total_expected_minutes=total,
        human_equivalent_minutes=human_equivalent_minutes,
        metr_warning=metr_warning,
        estimation_category=EstimationCategory.DOCUMENTATION,
    )
