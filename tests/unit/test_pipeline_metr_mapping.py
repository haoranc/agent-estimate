"""Pipeline-level tests for METR model-key mapping behavior."""

from __future__ import annotations

from agent_estimate.cli.commands import _pipeline
from agent_estimate.cli.commands._pipeline import run_estimate_pipeline
from agent_estimate.core.models import (
    AgentProfile,
    EstimationConfig,
    ProjectSettings,
    ReviewMode,
    SizeTier,
    SizingResult,
    TaskType,
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


def _claude_frontier_config_with_friction(friction: float) -> EstimationConfig:
    config = _claude_frontier_config()
    return EstimationConfig(
        agents=config.agents,
        settings=ProjectSettings(
            friction_multiplier=friction,
            inter_wave_overhead=0.0,
            review_overhead=0.0,
            metr_fallback_threshold=45.0,
        ),
    )


class TestPipelineMetrMapping:
    def test_claude_assigned_task_uses_opus_threshold(self, monkeypatch) -> None:
        monkeypatch.setattr(
            _pipeline,
            "classify_task",
            lambda _description: SizingResult(
                tier=SizeTier.XL,
                baseline_optimistic=90.0,
                baseline_most_likely=180.0,
                baseline_pessimistic=360.0,
                task_type=TaskType.FEATURE,
                signals=("test",),
            ),
        )
        report = run_estimate_pipeline(
            ["deterministic"],
            _claude_frontier_config(),
            review_mode=ReviewMode.NONE,
        )
        task = report.tasks[0]
        assert task.agent == "Claude"
        assert task.metr_warning is not None
        assert "opus" in task.metr_warning
        assert "(90m)" in task.metr_warning

    def test_no_false_positive_for_claude_task_at_or_below_90m(self, monkeypatch) -> None:
        monkeypatch.setattr(
            _pipeline,
            "classify_task",
            lambda _description: SizingResult(
                tier=SizeTier.S,
                baseline_optimistic=12.0,
                baseline_most_likely=23.0,
                baseline_pessimistic=40.0,
                task_type=TaskType.FEATURE,
                signals=("test",),
            ),
        )
        report = run_estimate_pipeline(
            ["deterministic"],
            _claude_frontier_config(),
            review_mode=ReviewMode.STANDARD,
        )
        task = report.tasks[0]
        assert task.agent == "Claude"
        assert task.metr_warning is None

    def test_assigned_task_metr_recheck_includes_friction(self, monkeypatch) -> None:
        monkeypatch.setattr(
            _pipeline,
            "classify_task",
            lambda _description: SizingResult(
                tier=SizeTier.M,
                baseline_optimistic=30.0,
                baseline_most_likely=50.0,
                baseline_pessimistic=85.0,
                task_type=TaskType.FEATURE,
                signals=("test",),
            ),
        )

        report = run_estimate_pipeline(
            ["deterministic"],
            _claude_frontier_config_with_friction(2.0),
            review_mode=ReviewMode.STANDARD,
        )

        task = report.tasks[0]
        assert task.metr_warning is not None
        assert "Estimate (120m) exceeds opus_4_7 p80 threshold (90m)" in task.metr_warning
