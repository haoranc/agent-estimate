"""Session-level estimation for coordinated multi-agent workflows.

Models wall-clock vs agent-minutes distinction for parallel agent sessions
with sequential rounds and coordination overhead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# Task type duration stubs
# ---------------------------------------------------------------------------

#: Default per-agent duration (minutes) for each session task type.
#: These are conservative base estimates for a single round.
SESSION_TYPE_DURATIONS: dict[str, float] = {
    "coding": 50.0,
    "brainstorm": 10.0,
    "research": 30.0,
    "config": 20.0,
    "documentation": 30.0,
    "review": 15.0,
}

#: Default coordination overhead (minutes) added per round to account for
#: agent synchronization, message passing, and turn-taking latency.
DEFAULT_COORDINATION_OVERHEAD_MINUTES: float = 5.0

SessionTaskType = Literal[
    "coding", "brainstorm", "research", "config", "documentation", "review"
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionEstimate:
    """Estimation result for a multi-agent session."""

    agents: int
    """Number of parallel agents in the session."""

    rounds: int
    """Number of sequential rounds."""

    task_type: str
    """Task type key used for per-round duration lookup."""

    per_agent_round_minutes: float
    """Duration one agent spends per round (before parallelism)."""

    coordination_overhead_minutes: float
    """Coordination overhead added per round (wall-clock)."""

    wall_clock_minutes: float
    """Total wall-clock time: sum over rounds of (max_round_duration + overhead)."""

    agent_minutes: float
    """Total agent-minutes: sum of all individual agent durations across all rounds."""

    rounds_breakdown: tuple[float, ...]
    """Wall-clock duration for each round (excludes per-round overhead)."""


# ---------------------------------------------------------------------------
# Estimation logic
# ---------------------------------------------------------------------------


def estimate_session(
    agents: int,
    rounds: int,
    task_type: str = "brainstorm",
    coordination_overhead_minutes: float = DEFAULT_COORDINATION_OVERHEAD_MINUTES,
    per_round_minutes: float | None = None,
) -> SessionEstimate:
    """Estimate wall-clock and agent-minutes for a multi-agent session.

    Wall-clock is computed as::

        wall_clock = sum(max(round_durations_per_agent) + coordination_overhead)
                   = rounds * (per_agent_round_minutes + coordination_overhead)

    Because all agents run in parallel for the same duration per round,
    ``max(round_durations)`` simplifies to ``per_agent_round_minutes``.

    Agent-minutes reflects total compute consumed::

        agent_minutes = rounds * agents * per_agent_round_minutes

    Args:
        agents: Number of parallel agents.
        rounds: Number of sequential rounds.
        task_type: Session task type key (brainstorm, research, coding, etc.).
            Used to look up the per-agent per-round duration baseline.
        coordination_overhead_minutes: Overhead added per round for
            synchronization and turn-taking (wall-clock only).
        per_round_minutes: Override per-agent per-round duration. When
            provided, ``task_type`` lookup is skipped.

    Returns:
        A :class:`SessionEstimate` with wall-clock and agent-minutes.

    Raises:
        ValueError: If agents < 1, rounds < 1, or task_type is unknown
            and ``per_round_minutes`` is not provided.
        ValueError: If coordination_overhead_minutes < 0.
    """
    if agents < 1:
        raise ValueError(f"agents must be >= 1, got {agents}")
    if rounds < 1:
        raise ValueError(f"rounds must be >= 1, got {rounds}")
    if coordination_overhead_minutes < 0:
        raise ValueError(
            f"coordination_overhead_minutes must be >= 0, got {coordination_overhead_minutes}"
        )

    if per_round_minutes is not None:
        if per_round_minutes < 0:
            raise ValueError(
                f"per_round_minutes must be >= 0, got {per_round_minutes}"
            )
        round_duration = per_round_minutes
    else:
        task_type_lower = task_type.lower()
        if task_type_lower not in SESSION_TYPE_DURATIONS:
            known = ", ".join(sorted(SESSION_TYPE_DURATIONS))
            raise ValueError(
                f"Unknown task type: {task_type!r}. Known types: {known}"
            )
        round_duration = SESSION_TYPE_DURATIONS[task_type_lower]

    # All agents run the same task in parallel per round, so wall-clock per
    # round is round_duration (the max is trivially that value) plus overhead.
    rounds_breakdown = tuple(round_duration for _ in range(rounds))
    wall_clock = sum(rd + coordination_overhead_minutes for rd in rounds_breakdown)
    agent_minutes = rounds * agents * round_duration

    return SessionEstimate(
        agents=agents,
        rounds=rounds,
        task_type=task_type.lower() if per_round_minutes is None else task_type,
        per_agent_round_minutes=round_duration,
        coordination_overhead_minutes=coordination_overhead_minutes,
        wall_clock_minutes=wall_clock,
        agent_minutes=agent_minutes,
        rounds_breakdown=rounds_breakdown,
    )
