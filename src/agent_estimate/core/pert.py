"""PERT estimation calculations for AI agent tasks."""

from __future__ import annotations

import logging
import re
from importlib.resources import as_file, files
from typing import Mapping

import yaml

from agent_estimate.core.models import (
    MetrWarning,
    ModifierSet,
    PertResult,
    ReviewMode,
    SizingResult,
    TaskEstimate,
)
from agent_estimate.core.modifiers import apply_modifiers, compute_review_overhead

METR_THRESHOLDS_FILENAME = "metr_thresholds.yaml"
logger = logging.getLogger("agent_estimate")

_MODEL_KEY_ALIASES: dict[str, str] = {
    "opus": "opus",
    "claude": "opus",
    "claude_opus": "opus",
    "gpt_5_3": "gpt_5_3",
    "codex": "gpt_5_3",
    "production": "gpt_5_3",
    "gpt_5_2": "gpt_5_2",
    "gpt_5": "gpt_5",
    "gemini_3_pro": "gemini_3_pro",
    "gemini": "gemini_3_pro",
    "gemini_pro": "gemini_3_pro",
    "sonnet": "sonnet",
}


def _normalize_model_token(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def _resolve_threshold_model_key(model_key: str, *, agent_name: str | None = None) -> str:
    normalized_model = _normalize_model_token(model_key)
    if normalized_model in _MODEL_KEY_ALIASES:
        return _MODEL_KEY_ALIASES[normalized_model]

    if normalized_model == "frontier" and agent_name:
        normalized_agent = _normalize_model_token(agent_name)
        if "claude" in normalized_agent:
            return "opus"
        if "codex" in normalized_agent:
            return "gpt_5_3"
        if "gemini" in normalized_agent:
            return "gemini_3_pro"

    return normalized_model


def compute_pert(optimistic: float, most_likely: float, pessimistic: float) -> PertResult:
    """Compute PERT expected value and standard deviation.

    Formula: E = (O + 4M + P) / 6, sigma = (P - O) / 6
    """
    if not (optimistic <= most_likely <= pessimistic):
        raise ValueError(
            f"PERT requires O <= M <= P, got O={optimistic}, M={most_likely}, P={pessimistic}"
        )
    expected = (optimistic + 4 * most_likely + pessimistic) / 6
    sigma = (pessimistic - optimistic) / 6
    return PertResult(
        optimistic=optimistic,
        most_likely=most_likely,
        pessimistic=pessimistic,
        expected=expected,
        sigma=sigma,
    )


def load_metr_thresholds() -> dict[str, float]:
    """Load METR p80 thresholds from the packaged YAML file.

    Returns a dict mapping model_key -> p80_minutes.
    """
    resource = files("agent_estimate").joinpath(METR_THRESHOLDS_FILENAME)
    with as_file(resource) as path:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        return {
            key: float(entry["p80_minutes"])
            for key, entry in raw.get("models", {}).items()
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Malformed {METR_THRESHOLDS_FILENAME}: {exc}") from exc


def check_metr_threshold(
    model_key: str,
    estimated_minutes: float,
    *,
    thresholds: Mapping[str, float] | None = None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
) -> MetrWarning | None:
    """Check whether an estimate exceeds the METR p80 reliability threshold.

    Args:
        model_key: Concrete model identifier (e.g. "opus", "sonnet").
        estimated_minutes: The total estimated minutes for the task.
        thresholds: Optional pre-loaded thresholds dict. If None, loads from YAML.
        fallback_threshold: Used when model_key is not found in thresholds.
        agent_name: Optional assigned agent name for resolving legacy model tiers.

    Returns:
        A MetrWarning if the estimate exceeds the threshold, else None.
    """
    if thresholds is None:
        thresholds = load_metr_thresholds()

    resolved_model_key = _resolve_threshold_model_key(model_key, agent_name=agent_name)
    threshold = thresholds.get(resolved_model_key)
    if threshold is None:
        logger.warning(
            "METR threshold not found for model_key=%r (resolved=%r, agent_name=%r); "
            "using fallback_threshold=%.1f",
            model_key,
            resolved_model_key,
            agent_name,
            fallback_threshold,
        )
        threshold = fallback_threshold

    if estimated_minutes <= threshold:
        return None

    return MetrWarning(
        model_key=resolved_model_key,
        threshold_minutes=threshold,
        estimated_minutes=estimated_minutes,
        message=(
            f"Estimate ({estimated_minutes:.0f}m) exceeds {resolved_model_key} "
            f"p80 threshold ({threshold:.0f}m). Consider splitting the task."
        ),
    )


def estimate_task(
    sizing: SizingResult,
    modifiers: ModifierSet,
    *,
    review_mode: ReviewMode = ReviewMode.NONE,
    model_key: str = "opus",
    thresholds: Mapping[str, float] | None = None,
    fallback_threshold: float = 40.0,
    agent_name: str | None = None,
    human_equivalent_minutes: float | None = None,
) -> TaskEstimate:
    """Full estimation pipeline: sizing -> PERT -> modifiers -> review -> METR check.

    Args:
        sizing: Task sizing result with calibrated baselines.
        modifiers: Modifier set to apply to baselines.
        review_mode: Code review overhead model.
        model_key: Concrete model identifier for METR check.
        thresholds: Pre-loaded METR thresholds (optional).
        fallback_threshold: METR fallback when model_key is unknown.
        agent_name: Optional assigned agent name for resolving legacy model tiers.
        human_equivalent_minutes: Pre-computed human equivalent (optional).

    Returns:
        A complete TaskEstimate.
    """
    # All three baselines are scaled by the same combined modifier,
    # preserving the O/P ratio intentionally. Modifier uncertainty is
    # captured by the modifier ranges themselves, not PERT spread.
    adjusted_o = apply_modifiers(sizing.baseline_optimistic, modifiers)
    adjusted_m = apply_modifiers(sizing.baseline_most_likely, modifiers)
    adjusted_p = apply_modifiers(sizing.baseline_pessimistic, modifiers)

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
    )
