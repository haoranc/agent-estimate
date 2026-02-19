"""Dispatch history loading and warm_context inference."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("agent_estimate")


@dataclass(frozen=True)
class WarmContextResult:
    """Result of warm_context inference from dispatch history."""

    value: float
    source: str  # "auto" or "default"
    detail: str | None = None


def infer_warm_context(
    history_path: Path | None,
    *,
    agent: str | None = None,
    project: str | None = None,
    reference_time: datetime | None = None,
) -> WarmContextResult:
    """Infer warm_context from dispatch history.

    Args:
        history_path: Path to dispatch history JSON file.
        agent: Filter dispatches by agent name.
        project: Filter dispatches by project name.
        reference_time: Reference time for recency calculation (default: now).

    Returns:
        WarmContextResult with the inferred value and metadata.
    """
    if history_path is None:
        return WarmContextResult(value=1.0, source="default")

    dispatches = _load_dispatches(history_path)
    if not dispatches:
        return WarmContextResult(value=1.0, source="default")

    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    # Filter by agent and project if specified
    filtered = dispatches
    if agent is not None:
        filtered = [d for d in filtered if d.get("agent") == agent]
    if project is not None:
        filtered = [d for d in filtered if d.get("project") == project]

    if not filtered:
        return WarmContextResult(value=1.0, source="default")

    # Find the most recent dispatch by completed_at
    most_recent = None
    most_recent_time: datetime | None = None
    for d in filtered:
        completed_at = d.get("completed_at")
        if completed_at is None:
            continue
        try:
            dt = datetime.fromisoformat(completed_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if most_recent_time is None or dt > most_recent_time:
            most_recent_time = dt
            most_recent = d

    if most_recent is None or most_recent_time is None:
        return WarmContextResult(value=1.0, source="default")

    hours_ago = (reference_time - most_recent_time).total_seconds() / 3600.0

    value = _decay_to_warm_context(hours_ago)

    # Build detail string
    agent_name = most_recent.get("agent", "unknown")
    project_name = most_recent.get("project", "unknown")
    if hours_ago < 1:
        time_str = f"{int(hours_ago * 60)}m ago"
    else:
        time_str = f"{hours_ago:.0f}h ago"
    detail = f"{agent_name} active {time_str} on {project_name}"

    return WarmContextResult(value=value, source="auto", detail=detail)


def _decay_to_warm_context(hours_ago: float) -> float:
    """Map hours since last dispatch to a warm_context value.

    Decay bands:
        <2h  -> 0.3 (very warm)
        2-12h -> 0.5 (warm)
        12-24h -> 0.7 (lukewarm)
        >=24h -> 1.0 (cold)
    """
    if hours_ago < 2:
        return 0.3
    if hours_ago < 12:
        return 0.5
    if hours_ago < 24:
        return 0.7
    return 1.0


def _load_dispatches(path: Path) -> list[dict]:
    """Load dispatch records from a JSON file.

    Expected format: {"dispatches": [{"agent": ..., "project": ..., "completed_at": ...}, ...]}

    Returns an empty list on missing file, malformed JSON, or missing key.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("History file not found: %s", path)
        return []
    except OSError as exc:
        logger.warning("Error reading history file %s: %s", path, exc)
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Malformed JSON in history file %s: %s", path, exc)
        return []

    if not isinstance(data, dict):
        logger.warning("History file %s: expected object, got %s", path, type(data).__name__)
        return []

    dispatches = data.get("dispatches")
    if dispatches is None:
        logger.warning("History file %s: missing 'dispatches' key", path)
        return []

    if not isinstance(dispatches, list):
        logger.warning("History file %s: 'dispatches' is not a list", path)
        return []

    return [d for d in dispatches if isinstance(d, dict)]
