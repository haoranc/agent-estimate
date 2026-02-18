"""Human-speed equivalent calculations and reporting."""

from __future__ import annotations

import math

from agent_estimate.core.models import TaskType

# Human multiplier ranges by task type (low, high).
# Geometric mean is used as the point estimate.
_HUMAN_MULTIPLIERS: dict[TaskType, tuple[float, float]] = {
    TaskType.BOILERPLATE: (3.0, 5.0),
    TaskType.BUG_FIX: (1.5, 3.0),
    TaskType.FEATURE: (2.0, 4.0),
    TaskType.REFACTOR: (2.0, 3.5),
    TaskType.TEST: (2.5, 4.5),
    TaskType.DOCS: (3.0, 6.0),
    TaskType.UNKNOWN: (2.0, 4.0),
}


def get_human_multiplier(task_type: TaskType) -> float:
    """Return the geometric-mean human multiplier for a task type.

    The multiplier represents how many times longer a human would take
    compared to an AI agent for this category of work.
    """
    lo, hi = _HUMAN_MULTIPLIERS[task_type]
    return math.sqrt(lo * hi)


def compute_human_equivalent(agent_minutes: float, task_type: TaskType) -> float:
    """Compute the human-equivalent time in minutes.

    Args:
        agent_minutes: Estimated agent time in minutes.
        task_type: Category of work for multiplier lookup.

    Returns:
        Estimated human time in minutes.
    """
    return agent_minutes * get_human_multiplier(task_type)
