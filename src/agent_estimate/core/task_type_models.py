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
from agent_estimate.core.sizing import count_inline_file_references

# ---------------------------------------------------------------------------
# Auto-detection patterns for EstimationCategory
# ---------------------------------------------------------------------------

_RESEARCH_GROUNDED_BRAINSTORM_RE = re.compile(
    r"(?=.*\b(brainstorm|ideate|explore ideas?|spike|discovery)\b)"
    r"(?=.*\b(research|citation|citations|sources?|primary[- ]source|"
    r"evidence|oss|open[- ]source|github|compare|survey|benchmark|"
    r"landscape)\b)",
    re.IGNORECASE,
)

_CATEGORY_PATTERNS: list[tuple[re.Pattern[str], EstimationCategory]] = [
    # Research-grounded brainstorms must route to research before flat brainstorm.
    (_RESEARCH_GROUNDED_BRAINSTORM_RE, EstimationCategory.RESEARCH),
    # Config / SRE — infrastructure, deployment, ops
    (
        re.compile(
            r"\b(configure|configuration|deploy(?:ment)?|infra(?:structure)?|"
            r"sre|devops|terraform|helm|ansible|k8s|kubernetes|"
            r"ci/?cd|ci pipeline|deploy pipeline|monitoring|alerting|oncall|runbook|"
            r"config (?:file|change|update|migration|setting)|"
            r"env(?:ironment)? var(?:iable)?s?|secret(?:s| management)?)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.CONFIG_SRE,
    ),
    # Frontend/UI — page content patches and page/component builds
    (
        re.compile(
            r"\b(front[- ]?end|ui|ux|landing page|web page|page build|"
            r"component page|design system|mdx|seo snippet|structured data|"
            r"copy update|single[- ]section|hero section)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.FRONTEND,
    ),
    # App development — app shell, desktop/mobile apps, Electron/native shells
    (
        re.compile(
            r"\b(app[- ]?dev|app shell|desktop app|mobile app|electron|tauri|"
            r"native app|mac app|ios app|android app|application shell)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.APP_DEV,
    ),
    # Brainstorm — ideation, design, discussion
    (
        re.compile(
            r"\b(brainstorm|ideate|explore ideas?|design session|whiteboard|discuss|"
            r"spike|discovery|kickoff|alignment)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.BRAINSTORM,
    ),
    # Research — investigation, analysis, evaluation
    (
        re.compile(
            r"\b(research|investigate|analyze|analyse|survey|evaluate|"
            r"feasibility|benchmarks?|compare|assessment|audit)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.RESEARCH,
    ),
    # Documentation — writing, docs, readme
    (
        re.compile(
            r"\b(doc(?:umentation|s)?|readme|write up|write-up|changelog|"
            r"api docs?|wiki|confluence|technical writing|specification)\b",
            re.IGNORECASE,
        ),
        EstimationCategory.DOCUMENTATION,
    ),
]

_TITLE_PREFIX_RE = re.compile(r"^(?:\[[^\]]+\]\s*)+")
_CODING_TITLE_ACTION_RE = re.compile(
    r"^(?:fix|implement|add|update|replace|delete|remove|move|make|build|create|"
    r"generate|refactor|rename|install|ship|wire|land|migrate|deprecate|drop|"
    r"introduce|support|set up)\b",
    re.IGNORECASE,
)
_CATEGORY_TITLE_ACTIONS: dict[EstimationCategory, re.Pattern[str]] = {
    EstimationCategory.BRAINSTORM: re.compile(
        r"^(?:brainstorm|ideate|explore ideas?|spike|discovery|whiteboard)\b",
        re.IGNORECASE,
    ),
    EstimationCategory.RESEARCH: re.compile(
        r"^(?:research|investigate|analy[sz]e|survey|evaluate|feasibility|"
        r"benchmarks?|compare|assess|audit)\b",
        re.IGNORECASE,
    ),
    EstimationCategory.CONFIG_SRE: re.compile(
        r"^(?:configure|deploy|provision|set up|terraform)\b",
        re.IGNORECASE,
    ),
    EstimationCategory.FRONTEND: re.compile(
        r"^(?:build|create|design|update).*(?:front[- ]?end|ui|ux|page|mdx|"
        r"seo snippet|structured data)",
        re.IGNORECASE,
    ),
    EstimationCategory.APP_DEV: re.compile(
        r"^(?:build|create|design|update).*(?:app|electron|tauri|ios|android)",
        re.IGNORECASE,
    ),
    EstimationCategory.DOCUMENTATION: re.compile(
        r"^(?:write|update|generate|document).*(?:docs?|documentation|readme|"
        r"changelog|wiki|specification)",
        re.IGNORECASE,
    ),
}
_CODING_STRUCTURE_HEADING_RE = re.compile(
    r"(?im)^#{1,6}\s+(scope|done(?: criteria)?|acceptance(?: criteria)?|build)\b"
)
_CODING_CHANGE_RE = re.compile(
    r"\b(?:fixtures?|implementation|commits?|patch(?:es)?|source (?:file|code)|"
    r"modules?|functions?|classes?|schemas?)\b|"
    r"\b(?:add|update|replace|delete|remove|move|generate|refactor|rename|"
    r"migrate|drop|introduce|implement)\b[^\n.!?]{0,80}"
    r"(?:`[^`\n]+`|\b(?:files?|modules?|functions?|classes?|schemas?|"
    r"fixtures?|tests?|docs?)\b)",
    re.IGNORECASE,
)

_TITLE_CATEGORY_SCORE = 10
_CATEGORY_ACTION_SCORE = 40
_RESEARCH_GROUNDED_SCORE = 42

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

# Frontend/UI: bimodal content-patch vs page-build regimes
_FRONTEND_CONTENT_BASELINES = (15.0, 25.0, 40.0)
_FRONTEND_BUILD_BASELINES = (40.0, 60.0, 90.0)

# App development: generic cold L-style prior; modifiers collapse warm/specified work
_APP_DEV_BASELINES = (45.0, 95.0, 180.0)

# Category baselines scale more gently than coding PERT bands. The ratio is
# taken against each model's reference tier, preserving its calibrated shape.
_CATEGORY_TIER_SCALE = {
    SizeTier.XS: 0.5,
    SizeTier.S: 1.0,
    SizeTier.M: 1.5,
    SizeTier.L: 2.0,
    SizeTier.XL: 3.0,
}

# Depth keywords that push research to the "deep" band
_RESEARCH_DEEP_PATTERNS = re.compile(
    r"\b(deep|thorough|comprehensive|in[-\s]?depth|extensive|detailed|"
    r"literature review|systematic|full|complete)\b",
    re.IGNORECASE,
)

_FRONTEND_CONTENT_PATTERNS = re.compile(
    r"\b(content|copy|seo|snippet|structured data|metadata|mdx|markdown|"
    r"single[- ]section|text update|copy update|small patch|minor patch)\b",
    re.IGNORECASE,
)


def _split_title_body(text: str) -> tuple[str, str]:
    title, separator, body = text.strip().partition("\n")
    if not separator:
        return title, ""
    return title, body.strip()


def _normalized_title(title: str) -> str:
    return _TITLE_PREFIX_RE.sub("", title.strip())


def _first_body_sentence(body: str) -> str:
    without_headings = re.sub(r"(?m)^\s*#{1,6}\s+[^\n]+$", "", body).strip()
    if not without_headings:
        return ""
    return re.split(r"(?<=[.!?])\s+", without_headings, maxsplit=1)[0]


def _coding_evidence_score(title: str, body: str) -> int:
    """Score implementation-shaped evidence without trusting quoted provenance nouns."""
    score = 2
    if _CODING_TITLE_ACTION_RE.search(_normalized_title(title)):
        # An implementation imperative outweighs a non-coding noun elsewhere
        # in the title, while an explicit category action (score 40+) still wins.
        score += 18

    headings = {
        match.group(1).casefold()
        for match in _CODING_STRUCTURE_HEADING_RE.finditer(body)
    }
    score += min(len(headings), 2) * 2

    file_references = count_inline_file_references(f"{title}\n{body}")
    if file_references >= 2:
        score += 3
    if file_references >= 5:
        score += 2
    if _CODING_CHANGE_RE.search(body):
        score += 4
    return score


def detect_estimation_category(text: str) -> EstimationCategory:
    """Infer category by scoring title intent against implementation structure.

    Title-level imperatives carry the most weight. Body-only category nouns are
    weak evidence, so provenance lines and cited paths cannot override concrete
    Scope/Done sections, file references, tests, CI, or PR delivery language.
    """
    if not text or not text.strip():
        return EstimationCategory.CODING

    title, body = _split_title_body(text)
    normalized_title = _normalized_title(title)
    first_body_sentence = _first_body_sentence(body)
    scores: dict[EstimationCategory, int] = {
        EstimationCategory.CODING: _coding_evidence_score(title, body)
    }
    category_order: list[EstimationCategory] = []

    for pattern, category in _CATEGORY_PATTERNS:
        if category not in category_order:
            category_order.append(category)
        score = scores.get(category, 0)
        if pattern.search(body):
            score = max(score, 1)
        if pattern.search(normalized_title):
            score = max(score, _TITLE_CATEGORY_SCORE)
        action_pattern = _CATEGORY_TITLE_ACTIONS.get(category)
        if action_pattern is not None:
            if action_pattern.search(normalized_title):
                score = max(score, _CATEGORY_ACTION_SCORE)
            elif action_pattern.search(first_body_sentence):
                score = max(score, 12)
        if pattern is _RESEARCH_GROUNDED_BRAINSTORM_RE and pattern.search(
            normalized_title
        ):
            score = max(score, _RESEARCH_GROUNDED_SCORE)
        scores[category] = score

    category_order.append(EstimationCategory.CODING)
    return max(category_order, key=lambda category: scores.get(category, 0))


def _make_non_coding_sizing(
    o: float,
    m: float,
    p: float,
    label: str,
    *,
    task_type: TaskType = TaskType.UNKNOWN,
    tier: SizeTier = SizeTier.S,
    size_hint: SizingResult | None = None,
    reference_tier: SizeTier | None = None,
) -> SizingResult:
    """Build category baselines scaled by the shared task-size classifier."""
    baseline_tier = reference_tier or tier
    has_size_evidence = (
        size_hint is not None
        and "no-size-signals-default-M" not in size_hint.signals
    )
    if has_size_evidence:
        target_tier = size_hint.tier
        scale = (
            _CATEGORY_TIER_SCALE[target_tier]
            / _CATEGORY_TIER_SCALE[baseline_tier]
        )
        o, m, p = o * scale, m * scale, p * scale
        signals = tuple(
            dict.fromkeys(
                (label, f"category-size-{target_tier.value}", *size_hint.signals)
            )
        )
    elif size_hint is not None:
        target_tier = baseline_tier
        signals = tuple(
            dict.fromkeys((label, "category-size-neutral", *size_hint.signals))
        )
    else:
        target_tier = tier
        signals = (label,)
    return SizingResult(
        tier=target_tier,
        baseline_optimistic=o,
        baseline_most_likely=m,
        baseline_pessimistic=p,
        task_type=task_type,
        signals=signals,
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
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate a brainstorm / ideation task.

    Uses a flat ~10m model. Modifiers still apply so warm context and agent fit
    can reduce time for follow-up sessions.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _BRAINSTORM_BASELINES
    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        "brainstorm-flat-model",
        size_hint=size_hint,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate a research / investigation task.

    Uses a time-boxed model: 15-30m for shallow, 25-50m for deep research.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    if _RESEARCH_DEEP_PATTERNS.search(description or ""):
        o, m, p = _RESEARCH_BASELINES_DEEP
        label = "research-deep-model"
        reference_tier = SizeTier.M
    else:
        o, m, p = _RESEARCH_BASELINES_SHALLOW
        label = "research-shallow-model"
        reference_tier = SizeTier.S

    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        label,
        size_hint=size_hint,
        reference_tier=reference_tier,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate a config / SRE / infrastructure task.

    Uses a flat + verification model: ~15-30m.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _CONFIG_SRE_BASELINES
    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        "config-sre-flat-model",
        size_hint=size_hint,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate a documentation task.

    Uses a line-count-based model similar to coding but with a lower floor: 10-45m.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _DOCUMENTATION_BASELINES
    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        "documentation-model",
        task_type=TaskType.DOCS,
        size_hint=size_hint,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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


def estimate_frontend(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate a frontend/UI task.

    Frontend work is bimodal: content/patch tasks use a smaller band, while
    page/component builds use a larger page-build band.
    """
    if review_mode is None:
        review_mode = ReviewMode.NONE

    if _FRONTEND_CONTENT_PATTERNS.search(description or ""):
        o, m, p = _FRONTEND_CONTENT_BASELINES
        label = "frontend-content-model"
        tier = SizeTier.S
    else:
        o, m, p = _FRONTEND_BUILD_BASELINES
        label = "frontend-build-model"
        tier = SizeTier.M

    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        label,
        task_type=TaskType.FRONTEND,
        tier=tier,
        size_hint=size_hint,
        reference_tier=tier,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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
        estimation_category=EstimationCategory.FRONTEND,
    )


def estimate_app_dev(
    description: str,
    modifiers: ModifierSet,
    *,
    review_mode=None,
    model_key: str = "opus",
    thresholds=None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
    size_hint: SizingResult | None = None,
) -> TaskEstimate:
    """Estimate an app-development task using a generic cold L-style prior."""
    if review_mode is None:
        review_mode = ReviewMode.NONE

    o, m, p = _APP_DEV_BASELINES
    sizing = _make_non_coding_sizing(
        o,
        m,
        p,
        "app-dev-generic-l-model",
        task_type=TaskType.APP_DEV,
        tier=SizeTier.L,
        size_hint=size_hint,
        reference_tier=SizeTier.L,
    )
    o = sizing.baseline_optimistic
    m = sizing.baseline_most_likely
    p = sizing.baseline_pessimistic

    adjusted_o = o * modifiers.combined
    adjusted_m = m * modifiers.combined
    adjusted_p = p * modifiers.combined

    pert = compute_pert(adjusted_o, adjusted_m, adjusted_p)
    review_minutes = compute_review_overhead(review_mode)
    total = pert.expected + review_minutes

    metr_warning = check_metr_threshold(
        model_key,
        pert.expected,
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
        estimation_category=EstimationCategory.APP_DEV,
    )
