"""Tests for multi-agent session estimation."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from agent_estimate.cli.app import app
from agent_estimate.core.session import (
    DEFAULT_COORDINATION_OVERHEAD_MINUTES,
    SESSION_TYPE_DURATIONS,
    SessionEstimate,
    estimate_session,
)


# ---------------------------------------------------------------------------
# Core logic tests
# ---------------------------------------------------------------------------


class TestEstimateSessionFormula:
    """Verify wall-clock and agent-minutes formulae."""

    def test_brainstorm_3agents_2rounds(self) -> None:
        """3-agent 2-round brainstorm: ~15m wall-clock, 60m agent-minutes."""
        result = estimate_session(agents=3, rounds=2, task_type="brainstorm")
        # per_round = 10m (brainstorm default)
        # wall_clock = 2 * (10 + 5) = 30m
        # agent_minutes = 2 * 3 * 10 = 60m
        assert result.per_agent_round_minutes == 10.0
        assert result.wall_clock_minutes == pytest.approx(30.0)
        assert result.agent_minutes == pytest.approx(60.0)

    def test_2agent_review_loop(self) -> None:
        """2-agent review session, 3 rounds."""
        result = estimate_session(agents=2, rounds=3, task_type="review")
        # per_round = 15m, overhead = 5m
        # wall_clock = 3 * (15 + 5) = 60m
        # agent_minutes = 3 * 2 * 15 = 90m
        assert result.wall_clock_minutes == pytest.approx(60.0)
        assert result.agent_minutes == pytest.approx(90.0)

    def test_n_agent_blitz(self) -> None:
        """5-agent coding blitz, 1 round."""
        result = estimate_session(agents=5, rounds=1, task_type="coding")
        # per_round = 50m, overhead = 5m
        # wall_clock = 1 * (50 + 5) = 55m
        # agent_minutes = 1 * 5 * 50 = 250m
        assert result.wall_clock_minutes == pytest.approx(55.0)
        assert result.agent_minutes == pytest.approx(250.0)

    def test_single_agent_single_round(self) -> None:
        """Degenerate 1-agent 1-round case."""
        result = estimate_session(agents=1, rounds=1, task_type="research")
        # wall_clock = 30 + 5 = 35m
        # agent_minutes = 30m
        assert result.wall_clock_minutes == pytest.approx(35.0)
        assert result.agent_minutes == pytest.approx(30.0)

    def test_wall_clock_less_than_agent_minutes_for_multi_agent(self) -> None:
        """Wall-clock should be < agent-minutes when agents > 1."""
        result = estimate_session(agents=4, rounds=2, task_type="brainstorm")
        assert result.wall_clock_minutes < result.agent_minutes

    def test_coordination_overhead_zero(self) -> None:
        """Zero overhead: wall-clock = rounds * per_round."""
        result = estimate_session(
            agents=3, rounds=2, task_type="brainstorm", coordination_overhead_minutes=0
        )
        assert result.wall_clock_minutes == pytest.approx(
            2 * SESSION_TYPE_DURATIONS["brainstorm"]
        )

    def test_custom_coordination_overhead(self) -> None:
        """Custom overhead applies per round."""
        result = estimate_session(
            agents=2,
            rounds=3,
            task_type="brainstorm",
            coordination_overhead_minutes=10.0,
        )
        # wall_clock = 3 * (10 + 10) = 60m
        assert result.wall_clock_minutes == pytest.approx(60.0)

    def test_per_round_minutes_override(self) -> None:
        """Explicit per_round_minutes skips task type lookup."""
        result = estimate_session(agents=2, rounds=2, per_round_minutes=25.0)
        assert result.per_agent_round_minutes == pytest.approx(25.0)
        assert result.wall_clock_minutes == pytest.approx(2 * (25.0 + 5.0))
        assert result.agent_minutes == pytest.approx(2 * 2 * 25.0)

    def test_rounds_breakdown_length(self) -> None:
        """rounds_breakdown should have one entry per round."""
        result = estimate_session(agents=2, rounds=4, task_type="documentation")
        assert len(result.rounds_breakdown) == 4

    def test_rounds_breakdown_values(self) -> None:
        """Each breakdown entry should equal per_agent_round_minutes."""
        result = estimate_session(agents=2, rounds=3, task_type="config")
        per_round = SESSION_TYPE_DURATIONS["config"]
        assert all(rd == pytest.approx(per_round) for rd in result.rounds_breakdown)


class TestEstimateSessionReturnType:
    """Verify the return type fields are correct."""

    def test_returns_session_estimate(self) -> None:
        result = estimate_session(agents=2, rounds=1, task_type="brainstorm")
        assert isinstance(result, SessionEstimate)

    def test_fields_match_inputs(self) -> None:
        result = estimate_session(agents=3, rounds=2, task_type="research")
        assert result.agents == 3
        assert result.rounds == 2
        assert result.task_type == "research"
        assert result.coordination_overhead_minutes == DEFAULT_COORDINATION_OVERHEAD_MINUTES


class TestEstimateSessionValidation:
    """Verify input validation raises appropriate errors."""

    def test_zero_agents_raises(self) -> None:
        with pytest.raises(ValueError, match="agents must be >= 1"):
            estimate_session(agents=0, rounds=1)

    def test_negative_agents_raises(self) -> None:
        with pytest.raises(ValueError, match="agents must be >= 1"):
            estimate_session(agents=-1, rounds=1)

    def test_zero_rounds_raises(self) -> None:
        with pytest.raises(ValueError, match="rounds must be >= 1"):
            estimate_session(agents=1, rounds=0)

    def test_unknown_task_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown task type"):
            estimate_session(agents=1, rounds=1, task_type="unknown_type_xyz")

    def test_negative_overhead_raises(self) -> None:
        with pytest.raises(ValueError, match="coordination_overhead_minutes must be >= 0"):
            estimate_session(agents=1, rounds=1, coordination_overhead_minutes=-1.0)

    def test_negative_per_round_minutes_raises(self) -> None:
        with pytest.raises(ValueError, match="per_round_minutes must be >= 0"):
            estimate_session(agents=1, rounds=1, per_round_minutes=-5.0)

    def test_unknown_type_ok_when_per_round_provided(self) -> None:
        """Unknown task type is fine when per_round_minutes is provided."""
        result = estimate_session(
            agents=1, rounds=1, task_type="anything", per_round_minutes=20.0
        )
        assert result.per_agent_round_minutes == pytest.approx(20.0)


class TestAllKnownTaskTypes:
    """All known task types should resolve without error."""

    @pytest.mark.parametrize("task_type", list(SESSION_TYPE_DURATIONS.keys()))
    def test_known_type(self, task_type: str) -> None:
        result = estimate_session(agents=2, rounds=2, task_type=task_type)
        assert result.per_agent_round_minutes == SESSION_TYPE_DURATIONS[task_type]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


runner = CliRunner()


class TestSessionCLIMarkdown:
    """CLI session subcommand — markdown output."""

    def test_default_brainstorm(self) -> None:
        result = runner.invoke(app, ["session", "--agents", "3", "--rounds", "2"])
        assert result.exit_code == 0
        assert "Session Estimate" in result.output
        assert "Wall-clock" in result.output
        assert "Agent-minutes" in result.output

    def test_explicit_type(self) -> None:
        result = runner.invoke(
            app, ["session", "--agents", "2", "--rounds", "1", "--type", "research"]
        )
        assert result.exit_code == 0
        assert "research" in result.output

    def test_round_breakdown_multi_round(self) -> None:
        result = runner.invoke(
            app, ["session", "--agents", "2", "--rounds", "3", "--type", "brainstorm"]
        )
        assert result.exit_code == 0
        assert "Round breakdown" in result.output
        assert "Round 1" in result.output
        assert "Round 3" in result.output

    def test_single_round_no_breakdown(self) -> None:
        result = runner.invoke(
            app, ["session", "--agents", "2", "--rounds", "1", "--type", "brainstorm"]
        )
        assert result.exit_code == 0
        assert "Round breakdown" not in result.output

    def test_coordination_overhead_flag(self) -> None:
        result = runner.invoke(
            app,
            [
                "session",
                "--agents", "2",
                "--rounds", "1",
                "--type", "brainstorm",
                "--coordination-overhead", "0",
            ],
        )
        assert result.exit_code == 0

    def test_per_round_minutes_flag(self) -> None:
        result = runner.invoke(
            app,
            [
                "session",
                "--agents", "2",
                "--rounds", "2",
                "--per-round-minutes", "15",
            ],
        )
        assert result.exit_code == 0


class TestSessionCLIJson:
    """CLI session subcommand — JSON output."""

    def test_json_output_structure(self) -> None:
        result = runner.invoke(
            app,
            ["session", "--agents", "3", "--rounds", "2", "--type", "brainstorm", "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["agents"] == 3
        assert data["rounds"] == 2
        assert data["task_type"] == "brainstorm"
        assert "wall_clock_minutes" in data
        assert "agent_minutes" in data
        assert "rounds_breakdown" in data
        assert len(data["rounds_breakdown"]) == 2

    def test_json_values_match_formula(self) -> None:
        result = runner.invoke(
            app,
            ["session", "--agents", "3", "--rounds", "2", "--type", "brainstorm", "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # wall_clock = 2 * (10 + 5) = 30m
        assert data["wall_clock_minutes"] == pytest.approx(30.0)
        # agent_minutes = 2 * 3 * 10 = 60m
        assert data["agent_minutes"] == pytest.approx(60.0)


class TestSessionCLIErrors:
    """CLI session subcommand — error handling."""

    def test_unknown_format(self) -> None:
        result = runner.invoke(app, ["session", "--format", "xml"])
        assert result.exit_code != 0

    def test_unknown_task_type(self) -> None:
        result = runner.invoke(app, ["session", "--type", "unknown_xyz"])
        assert result.exit_code != 0
