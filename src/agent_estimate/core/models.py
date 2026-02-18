"""Pydantic models for estimation configuration and result dataclasses."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


# ---------------------------------------------------------------------------
# Pydantic config models (input validation)
# ---------------------------------------------------------------------------


class AgentProfile(BaseModel):
    """Configuration for one estimation agent profile."""

    model_config = ConfigDict(extra="forbid")

    name: NonEmptyStr
    capabilities: list[NonEmptyStr] = Field(min_length=1)
    parallelism: Annotated[int, Field(ge=1)]
    cost_per_turn: Annotated[float, Field(ge=0)]
    model_tier: NonEmptyStr


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
    """Code-review overhead model."""

    NONE = "none"
    SELF = "self"
    TWO_LGTM = "2x-lgtm"


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

    spec_clarity: float  # multiplier (0.8–1.3)
    warm_context: float  # multiplier (0.85–1.15)
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
