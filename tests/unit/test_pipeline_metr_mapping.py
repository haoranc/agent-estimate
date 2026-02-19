"""Pipeline-level tests for METR model-key mapping behavior."""

from __future__ import annotations

from agent_estimate.cli.commands._pipeline import run_estimate_pipeline
from agent_estimate.core.models import (
    AgentProfile,
    EstimationConfig,
    ProjectSettings,
    ReviewMode,
)


def _claude_frontier_config() -> EstimationConfig:
    return EstimationConfig(
        agents=[
            AgentProfile(
                name="Claude",
                capabilities=["planning", "implementation"],
                parallelism=1,
                cost_per_turn=0.12,
                model_tier="frontier",
            )
        ],
        settings=ProjectSettings(
            friction_multiplier=1.0,
            inter_wave_overhead=0.0,
            review_overhead=0.0,
            metr_fallback_threshold=45.0,
        ),
    )


class TestPipelineMetrMapping:
    def test_claude_assigned_task_uses_opus_threshold(self) -> None:
        report = run_estimate_pipeline(
            ["Massive rewrite auth pipeline"],
            _claude_frontier_config(),
            review_mode=ReviewMode.NONE,
        )
        task = report.tasks[0]
        assert task.agent == "Claude"
        assert task.metr_warning is not None
        assert "opus" in task.metr_warning
        assert "(90m)" in task.metr_warning

    def test_no_false_positive_for_claude_task_at_or_below_90m(self) -> None:
        report = run_estimate_pipeline(
            ["do the thing with the stuff"],
            _claude_frontier_config(),
            review_mode=ReviewMode.TWO_LGTM,
        )
        task = report.tasks[0]
        assert task.agent == "Claude"
        assert task.metr_warning is None
