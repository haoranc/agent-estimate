"""Task sizing heuristics and complexity mapping."""

from __future__ import annotations

import re

from agent_estimate.core.models import SizeTier, SizingResult, TaskType

# Calibrated baselines (minutes): optimistic, most_likely, pessimistic
TIER_BASELINES: dict[SizeTier, tuple[float, float, float]] = {
    SizeTier.XS: (5.0, 10.0, 20.0),
    SizeTier.S: (12.0, 23.0, 40.0),
    SizeTier.M: (25.0, 50.0, 90.0),
    SizeTier.L: (45.0, 95.0, 180.0),
    SizeTier.XL: (90.0, 180.0, 360.0),
}

# Signal words / patterns for size classification
_SIZE_SIGNALS: list[tuple[re.Pattern[str], SizeTier, str]] = [
    (re.compile(r"\b(trivial|typo|one[- ]?liner|rename)\b", re.I), SizeTier.XS, "trivial-keyword"),
    (re.compile(r"\b(small|simple|quick|minor|stub)\b", re.I), SizeTier.S, "small-keyword"),
    (re.compile(r"\b(medium|moderate|standard|typical)\b", re.I), SizeTier.M, "medium-keyword"),
    (re.compile(r"\b(large|complex|multi[- ]?file|significant)\b", re.I), SizeTier.L, "large-keyword"),
    (re.compile(r"\b(epic|massive|rewrite|overhaul|redesign)\b", re.I), SizeTier.XL, "epic-keyword"),
]

# Complexity signals that push the tier up
_COMPLEXITY_SIGNALS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(database|migration|schema)\b", re.I), "database-change"),
    (re.compile(r"\b(security|auth|encrypt|token)\b", re.I), "security-concern"),
    (re.compile(r"\b(api|endpoint|rest|graphql)\b", re.I), "api-surface"),
    (re.compile(r"\b(test|coverage|ci|pipeline)\b", re.I), "test-infra"),
    (re.compile(r"\b(refactor|restructure|architecture)\b", re.I), "structural-change"),
]

# Task-type detection patterns
_TYPE_PATTERNS: list[tuple[re.Pattern[str], TaskType]] = [
    (re.compile(r"\b(boilerplate|scaffold|template|stub|generate)\b", re.I), TaskType.BOILERPLATE),
    (re.compile(r"\b(bug|fix|patch|hotfix|regression|broken)\b", re.I), TaskType.BUG_FIX),
    (re.compile(r"\b(feature|implement|add|create|build|new)\b", re.I), TaskType.FEATURE),
    (re.compile(r"\b(refactor|restructure|clean|rewrite|simplify)\b", re.I), TaskType.REFACTOR),
    (re.compile(r"\b(test|spec|coverage|assertion)\b", re.I), TaskType.TEST),
    (re.compile(r"\b(doc|readme|comment|changelog)\b", re.I), TaskType.DOCS),
]

_TIER_ORDER = [SizeTier.XS, SizeTier.S, SizeTier.M, SizeTier.L, SizeTier.XL]


def _detect_task_type(text: str) -> TaskType:
    """Detect the task type from description text."""
    for pattern, task_type in _TYPE_PATTERNS:
        if pattern.search(text):
            return task_type
    return TaskType.UNKNOWN


def _bump_tier(tier: SizeTier, steps: int = 1) -> SizeTier:
    """Move a tier up by the given number of steps, clamping at XL."""
    idx = _TIER_ORDER.index(tier)
    new_idx = min(idx + steps, len(_TIER_ORDER) - 1)
    return _TIER_ORDER[new_idx]


def classify_task(description: str) -> SizingResult:
    """Classify a task description into a size tier with calibrated baselines.

    Scans for signal words to determine a base tier, then applies complexity
    bumps. Returns a SizingResult with the final tier and baselines.
    """
    if not description or not description.strip():
        o, m, p = TIER_BASELINES[SizeTier.M]
        return SizingResult(
            tier=SizeTier.M,
            baseline_optimistic=o,
            baseline_most_likely=m,
            baseline_pessimistic=p,
            task_type=TaskType.UNKNOWN,
            signals=("no-description-default-M",),
        )

    signals: list[str] = []
    tier_votes: list[SizeTier] = []

    # Collect size signal votes
    for pattern, tier, signal_name in _SIZE_SIGNALS:
        if pattern.search(description):
            tier_votes.append(tier)
            signals.append(signal_name)

    # Base tier: median of votes, or M as default
    if tier_votes:
        sorted_votes = sorted(tier_votes, key=lambda t: _TIER_ORDER.index(t))
        base_tier = sorted_votes[len(sorted_votes) // 2]
    else:
        base_tier = SizeTier.M
        signals.append("no-size-signals-default-M")

    # Complexity bumps
    complexity_count = 0
    for pattern, signal_name in _COMPLEXITY_SIGNALS:
        if pattern.search(description):
            complexity_count += 1
            signals.append(signal_name)

    # Bump tier by 1 for every 2 complexity signals
    bump_steps = complexity_count // 2
    final_tier = _bump_tier(base_tier, bump_steps) if bump_steps > 0 else base_tier

    task_type = _detect_task_type(description)
    o, m, p = TIER_BASELINES[final_tier]

    return SizingResult(
        tier=final_tier,
        baseline_optimistic=o,
        baseline_most_likely=m,
        baseline_pessimistic=p,
        task_type=task_type,
        signals=tuple(signals),
    )
