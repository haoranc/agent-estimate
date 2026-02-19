"""End-to-end CLI integration tests using Typer's CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agent_estimate.cli.app import app

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_flag_prints_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "agent-estimate" in result.output

    def test_version_flag_short_form_not_supported(self) -> None:
        # Typer only supports --version (no -V by default)
        result = runner.invoke(app, ["-V"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Estimate — single task
# ---------------------------------------------------------------------------


class TestEstimateSingleTask:
    def test_estimate_single_task_default_config(self) -> None:
        result = runner.invoke(app, ["estimate", "Add login button"])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_single_task_with_config(self) -> None:
        config = str(FIXTURES / "simple_linear.yaml")
        result = runner.invoke(app, ["estimate", "--config", config, "Add login button"])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_single_task_parallel_config(self) -> None:
        config = str(FIXTURES / "parallel_fanout.yaml")
        result = runner.invoke(app, ["estimate", "--config", config, "Build REST API"])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_single_task_minimal_config(self) -> None:
        config = str(FIXTURES / "minimal_agents.yaml")
        result = runner.invoke(app, ["estimate", "--config", config, "Fix typo"])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_custom_title(self) -> None:
        result = runner.invoke(
            app, ["estimate", "--title", "My Custom Report", "Add login button"]
        )
        assert result.exit_code == 0
        assert "My Custom Report" in result.output


# ---------------------------------------------------------------------------
# Estimate — file input
# ---------------------------------------------------------------------------


class TestEstimateFileInput:
    def test_estimate_file_input(self) -> None:
        task_file = str(FIXTURES / "tasks_multi.txt")
        result = runner.invoke(app, ["estimate", "--file", task_file])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_file_with_config(self) -> None:
        task_file = str(FIXTURES / "tasks_multi.txt")
        config = str(FIXTURES / "parallel_fanout.yaml")
        result = runner.invoke(app, ["estimate", "--file", task_file, "--config", config])
        assert result.exit_code == 0
        assert "Agent Estimate Report" in result.output

    def test_estimate_file_not_found(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "nonexistent.txt")
        result = runner.invoke(app, ["estimate", "--file", missing])
        assert result.exit_code != 0
        assert "File not found" in result.output


# ---------------------------------------------------------------------------
# Estimate — review modes
# ---------------------------------------------------------------------------


class TestEstimateReviewModes:
    def test_review_mode_none(self) -> None:
        result = runner.invoke(app, ["estimate", "--review-mode", "none", "Add button"])
        assert result.exit_code == 0

    def test_review_mode_self(self) -> None:
        result = runner.invoke(app, ["estimate", "--review-mode", "self", "Add button"])
        assert result.exit_code == 0

    def test_review_mode_2x_lgtm(self) -> None:
        result = runner.invoke(app, ["estimate", "--review-mode", "2x-lgtm", "Add button"])
        assert result.exit_code == 0

    def test_review_mode_invalid(self) -> None:
        result = runner.invoke(app, ["estimate", "--review-mode", "bogus", "Add button"])
        assert result.exit_code != 0
        assert "Invalid review mode" in result.output


# ---------------------------------------------------------------------------
# Estimate — format
# ---------------------------------------------------------------------------


class TestEstimateFormat:
    def test_format_markdown(self) -> None:
        result = runner.invoke(app, ["estimate", "--format", "markdown", "Add button"])
        assert result.exit_code == 0

    def test_format_json_not_implemented(self) -> None:
        result = runner.invoke(app, ["estimate", "--format", "json", "Add button"])
        assert result.exit_code != 0
        assert "not yet implemented" in result.output

    def test_format_unknown(self) -> None:
        result = runner.invoke(app, ["estimate", "--format", "xml", "Add button"])
        assert result.exit_code != 0
        assert "Unknown format" in result.output


# ---------------------------------------------------------------------------
# Estimate — error cases
# ---------------------------------------------------------------------------


class TestEstimateErrors:
    def test_no_input_shows_error(self) -> None:
        result = runner.invoke(app, ["estimate"])
        assert result.exit_code != 0

    def test_task_and_file_mutual_exclusion(self, tmp_path: Path) -> None:
        task_file = tmp_path / "tasks.txt"
        task_file.write_text("Some task\n")
        result = runner.invoke(
            app, ["estimate", "inline task", "--file", str(task_file)]
        )
        assert result.exit_code != 0
        assert "only one input source" in result.output.lower() or "Provide only one" in result.output

    def test_config_file_not_found(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "no_such_config.yaml")
        result = runner.invoke(app, ["estimate", "--config", missing, "task"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_config_invalid_validation(self) -> None:
        config = str(FIXTURES / "cycle_invalid.yaml")
        result = runner.invoke(app, ["estimate", "--config", config, "task"])
        assert result.exit_code != 0

    def test_config_empty_agents(self) -> None:
        config = str(FIXTURES / "malformed_missing_agent.yaml")
        result = runner.invoke(app, ["estimate", "--config", config, "task"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Calibrate
# ---------------------------------------------------------------------------


class TestCalibrate:
    def test_calibrate_no_db(self) -> None:
        result = runner.invoke(app, ["calibrate"])
        assert result.exit_code != 0
        assert "No calibration database" in result.output

    def test_calibrate_nonexistent_db(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "missing.db")
        result = runner.invoke(app, ["calibrate", "--db", db_path])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_validate_valid_observation(self) -> None:
        obs = str(FIXTURES / "observation_valid.yaml")
        result = runner.invoke(app, ["validate", obs])
        assert result.exit_code == 0
        assert "Estimation vs Actual Comparison" in result.output
        assert "ACCURATE" in result.output

    def test_validate_file_not_found(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "nope.yaml")
        result = runner.invoke(app, ["validate", missing])
        assert result.exit_code != 0
        assert "File not found" in result.output

    def test_validate_malformed_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("not: a: valid: yaml: [")
        result = runner.invoke(app, ["validate", str(bad)])
        assert result.exit_code != 0

    def test_validate_missing_required_fields(self, tmp_path: Path) -> None:
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("task_type: feature\n")
        result = runner.invoke(app, ["validate", str(incomplete)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# No args / help
# ---------------------------------------------------------------------------


class TestNoArgs:
    def test_no_args_shows_usage(self) -> None:
        result = runner.invoke(app, [])
        # no_args_is_help=True causes Click/Typer to exit with code 2
        assert "usage" in result.output.lower() or "estimate" in result.output.lower()

    def test_help_flag(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "estimate" in result.output.lower()

    def test_estimate_help(self) -> None:
        result = runner.invoke(app, ["estimate", "--help"])
        assert result.exit_code == 0
        assert "task" in result.output.lower()
