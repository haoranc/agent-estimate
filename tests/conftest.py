"""Shared fixtures for agent_estimate test suite."""

from __future__ import annotations

import pytest

from agent_estimate.core.models import (
    AgentProfile,
    EstimationConfig,
    ModifierSet,
    ProjectSettings,
    SizeTier,
    SizingResult,
    TaskType,
)
from agent_estimate.core.modifiers import build_modifier_set
from agent_estimate.core.sizing import TIER_BASELINES


@pytest.fixture
def sample_agent_profile() -> AgentProfile:
    """A valid AgentProfile for use in tests."""
    return AgentProfile(
        name="Claude",
        capabilities=["code", "planning"],
        parallelism=2,
        cost_per_turn=0.12,
        model_tier="frontier",
    )


@pytest.fixture
def sample_project_settings() -> ProjectSettings:
    """A valid ProjectSettings for use in tests."""
    return ProjectSettings(
        friction_multiplier=1.1,
        inter_wave_overhead=0.25,
        review_overhead=0.15,
        metr_fallback_threshold=40.0,
    )


@pytest.fixture
def sample_estimation_config(
    sample_agent_profile: AgentProfile,
    sample_project_settings: ProjectSettings,
) -> EstimationConfig:
    """A valid EstimationConfig with one agent."""
    return EstimationConfig(
        agents=[sample_agent_profile],
        settings=sample_project_settings,
    )


@pytest.fixture
def neutral_modifier_set() -> ModifierSet:
    """All modifiers at 1.0 — neutral, combined=1.0."""
    return build_modifier_set()


@pytest.fixture
def sample_sizing_result() -> SizingResult:
    """A SizingResult for a medium FEATURE task."""
    o, m, p = TIER_BASELINES[SizeTier.M]
    return SizingResult(
        tier=SizeTier.M,
        baseline_optimistic=o,
        baseline_most_likely=m,
        baseline_pessimistic=p,
        task_type=TaskType.FEATURE,
        signals=("test-fixture",),
    )
