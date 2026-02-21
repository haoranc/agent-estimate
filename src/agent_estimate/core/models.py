"""Pydantic models for estimation configuration and result dataclasses."""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# ---------------------------------------------------------------------------
# Pydantic config models (input validation)
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentProfileProtocol(Protocol):
    """Runtime plugin protocol for discoverable agent profiles."""

    name: str
    capabilities: Sequence[str]
    parallelism: int
    cost_per_turn: float
    model_tier: str

    def adjust_estimate(self, minutes: float) -> float:
        """Optionally adjust an estimate (in minutes) for this profile."""


class AgentProfile(BaseModel):
    """Configuration for one estimation agent profile."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyStr
    capabilities: list[NonEmptyStr] = Field(min_length=1)
    parallelism: Annotated[int, Field(ge=1)]
    cost_per_turn: Annotated[float, Field(ge=0)]
    model_tier: NonEmptyStr

    def adjust_estimate(self, minutes: float) -> float:
        """Default profile adjustment: identity transform."""
        if minutes < 0:
            raise ValueError(f"minutes must be >= 0, got {minutes}")
        return float(minutes)


class ProjectSettings(BaseModel):
    """Project-level calibration and overhead settings."""

    model_config = ConfigDict(extra="forbid")

    friction_multiplier: Annotated[float, Field(gt=0)]
    inter_wave_overhead: Annotated[float, Field(ge=0)]
    review_overhead: Annotated[float, Field(ge=0)]
    metr_fallback_threshold: Annotated[float, Field(gt=0)]


class EstimationConfig(BaseModel):
    """Top-level config object for estimation inputs."""

    model_config = ConfigDict(extra="forbid")

    agents: list[AgentProfile] = Field(min_length=1)
    settings: ProjectSettings


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SizeTier(enum.Enum):
    """Task size classification."""

    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class TaskType(enum.Enum):
    """Category of work for human-comparison multipliers."""

    BOILERPLATE = "boilerplate"
    BUG_FIX = "bug_fix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    UNKNOWN = "unknown"


class ReviewMode(enum.Enum):
    """Code-review overhead model (additive minutes).

    NONE     — self-merge, no cross-agent review (0 m)
    STANDARD — clean 2x-LGTM, 1-2 rounds        (15 m)
    COMPLEX  — 3+ rounds, security-sensitive     (25 m)

    Legacy aliases kept for backwards compatibility:
      "self"    → NONE (maps to 0 m; was previously 7.5 m)
      "2x-lgtm" → STANDARD
    """

    NONE = "none"
    STANDARD = "standard"
    COMPLEX = "complex"

    @classmethod
    def _missing_(cls, value: object) -> "ReviewMode | None":
        """Accept legacy CLI values."""
        _legacy: dict[str, "ReviewMode"] = {
            "self": cls.NONE,
            "2x-lgtm": cls.STANDARD,
        }
        if isinstance(value, str):
            return _legacy.get(value)
        return None


# ---------------------------------------------------------------------------
# Result dataclasses (frozen, output-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PertResult:
    """Raw PERT computation output."""

    optimistic: float
    most_likely: float
    pessimistic: float
    expected: float
    sigma: float


@dataclass(frozen=True)
class SizingResult:
    """Tier assignment with calibrated baselines (minutes)."""

    tier: SizeTier
    baseline_optimistic: float
    baseline_most_likely: float
    baseline_pessimistic: float
    task_type: TaskType
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModifierSet:
    """Collected modifiers applied to a baseline estimate."""

    spec_clarity: float  # multiplier (0.3–1.3)
    warm_context: float  # multiplier (0.3–1.15)
    agent_fit: float  # multiplier (0.9–1.2)
    combined: float  # product of the three


@dataclass(frozen=True)
class MetrWarning:
    """Warning emitted when an estimate exceeds METR p80 threshold."""

    model_key: str
    threshold_minutes: float
    estimated_minutes: float
    message: str


@dataclass(frozen=True)
class TaskEstimate:
    """Full estimation result for one task."""

    sizing: SizingResult
    pert: PertResult
    modifiers: ModifierSet
    review_minutes: float
    total_expected_minutes: float
    human_equivalent_minutes: float | None
    metr_warning: MetrWarning | None


# ---------------------------------------------------------------------------
# Wave planner dataclasses (frozen, output-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskNode:
    """Input: one task to be scheduled."""

    task_id: str
    duration_minutes: float
    dependencies: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class WaveAssignment:
    """One task assigned to an agent slot within a wave."""

    task_id: str
    agent_name: str
    slot_index: int
    duration_minutes: float
    co_dispatch_group: tuple[str, ...] = ()
    """Task IDs co-dispatched to the same agent in the same wave.

    Non-empty only when two or more tasks are assigned to the same agent within
    a single wave.  The first task in the group receives no warm-context
    reduction; subsequent tasks have their ``duration_minutes`` reduced by 0.5x
    to model implicit warm context carried over from the first task.
    """


@dataclass(frozen=True)
class Wave:
    """A single scheduling wave."""

    wave_number: int
    start_minutes: float
    end_minutes: float
    assignments: tuple[WaveAssignment, ...]


@dataclass(frozen=True)
class WavePlan:
    """Complete wave plan output."""

    waves: tuple[Wave, ...]
    critical_path: tuple[str, ...]
    critical_path_minutes: float
    agent_utilization: Mapping[str, float]
    parallel_efficiency: float
    total_wall_clock_minutes: float
    total_sequential_minutes: float
