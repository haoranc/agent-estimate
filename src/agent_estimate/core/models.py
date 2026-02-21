"""Pydantic models for estimation configuration and result dataclasses."""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
import dataclasses
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


class EstimationCategory(enum.Enum):
    """Top-level task category that determines which estimation model to use.

    CODING       — default; uses PERT tiers (XS-XL) with modifiers
    BRAINSTORM   — flat model; ~10m independent, ~5m synthesis
    RESEARCH     — time-boxed; 15-45m depending on depth
    CONFIG_SRE   — flat + verification; ~15-30m
    DOCUMENTATION — line-count based; similar to coding but lower floor
    """

    CODING = "coding"
    BRAINSTORM = "brainstorm"
    RESEARCH = "research"
    CONFIG_SRE = "config"
    DOCUMENTATION = "documentation"


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
    combined: float  # clamped product (floor applied)
    raw_combined: float  # raw product before floor
    clamped: bool  # True when floor was applied


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
    estimation_category: "EstimationCategory | None" = None


# ---------------------------------------------------------------------------
# Wave planner dataclasses (frozen, output-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskNode:
    """Input: one task to be scheduled.

    ``duration_minutes`` is the work-only duration (no review).
    ``review_minutes`` is the per-task review overhead; the wave planner
    amortizes this across same-agent tasks in each wave so only a single
    review cycle is charged per agent per wave.
    """

    task_id: str
    duration_minutes: float
    dependencies: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    review_minutes: float = 0.0


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
    """A single scheduling wave.

    ``agent_review_minutes`` maps each agent to the single amortized review
    cycle charged for that agent in this wave (0.0 when review_mode is NONE
    or the agent has no tasks in the wave).
    """

    wave_number: int
    start_minutes: float
    end_minutes: float
    assignments: tuple[WaveAssignment, ...]
    agent_review_minutes: Mapping[str, float] = dataclasses.field(default_factory=dict)  # type: ignore[assignment]


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
