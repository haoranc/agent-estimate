"""Pydantic models for estimation configuration."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
