"""Runtime and risk modifiers for baseline estimates."""

from __future__ import annotations

from agent_estimate.core.models import ModifierSet, ReviewMode

# Review overhead constants (additive, minutes)
_REVIEW_OVERHEAD: dict[ReviewMode, float] = {
    ReviewMode.NONE: 0.0,
    ReviewMode.SELF: 7.5,
    ReviewMode.TWO_LGTM: 17.5,
}


def build_modifier_set(
    *,
    spec_clarity: float = 1.0,
    warm_context: float = 1.0,
    agent_fit: float = 1.0,
) -> ModifierSet:
    """Build a modifier set from individual factors.

    Args:
        spec_clarity: How clear/complete the spec is (0.3=crystal clear spec with design doc,
            1.0=normal, 1.3=vague).
        warm_context: Whether the agent has prior context (0.3=agent just completed closely
            related work, 0.5=same project recently, 1.0=cold, 1.15=very cold/new domain).
        agent_fit: How well the agent suits this task type (0.9=great, 1.2=poor).

    Raises:
        ValueError: If any modifier is outside its valid range.
    """
    _validate_range("spec_clarity", spec_clarity, 0.3, 1.3)
    _validate_range("warm_context", warm_context, 0.3, 1.15)
    _validate_range("agent_fit", agent_fit, 0.9, 1.2)

    combined = spec_clarity * warm_context * agent_fit
    return ModifierSet(
        spec_clarity=spec_clarity,
        warm_context=warm_context,
        agent_fit=agent_fit,
        combined=combined,
    )


def apply_modifiers(
    base_minutes: float,
    modifiers: ModifierSet,
) -> float:
    """Apply a modifier set to a base estimate."""
    return base_minutes * modifiers.combined


def compute_review_overhead(review_mode: ReviewMode) -> float:
    """Return the additive review overhead in minutes."""
    return _REVIEW_OVERHEAD[review_mode]


def _validate_range(name: str, value: float, lo: float, hi: float) -> None:
    if not (lo <= value <= hi):
        raise ValueError(f"{name} must be between {lo} and {hi}, got {value}")
