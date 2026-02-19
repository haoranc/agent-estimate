"""End-to-end CLI integration tests using Typer's CliRunner."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from agent_estimate.cli.app import app
from agent_estimate.cli.commands import estimate as estimate_command

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


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


class TestEstimateModifierFlags:
    def test_modifier_flags_affect_report_for_text_input(self) -> None:
        result = runner.invoke(
            app,
            [
                "estimate",
                "--spec-clarity",
                "0.3",
                "--warm-context",
                "0.3",
                "Add login button",
            ],
        )
        assert result.exit_code == 0
        assert "spec 0.30 x warm 0.30 x fit 1.00 = 0.09" in result.output

    def test_modifier_flags_work_with_file_input(self) -> None:
        task_file = str(FIXTURES / "tasks_multi.txt")
        result = runner.invoke(
            app,
            [
                "estimate",
                "--file",
                task_file,
                "--spec-clarity",
                "0.6",
                "--warm-context",
                "0.5",
                "--agent-fit",
                "1.1",
            ],
        )
        assert result.exit_code == 0
        assert "spec 0.60 x warm 0.50 x fit 1.10 = 0.33" in result.output

    def test_modifier_flags_work_with_issues_input(self, monkeypatch) -> None:
        class _FakeGitHubAdapter:
            def fetch_task_descriptions_by_numbers(
                self, repo: str, issue_numbers: list[int]
            ) -> list[str]:
                assert repo == "haoranc/agent-estimate"
                assert issue_numbers == [11, 12]
                return ["Implement auth flow", "Add tests"]

        monkeypatch.setattr(estimate_command, "GitHubGhCliAdapter", _FakeGitHubAdapter)
        result = runner.invoke(
            app,
            [
                "estimate",
                "--issues",
                "11,12",
                "--repo",
                "haoranc/agent-estimate",
                "--spec-clarity",
                "0.7",
                "--warm-context",
                "0.6",
            ],
        )
        assert result.exit_code == 0
        assert result.output.count("spec 0.70 x warm 0.60 x fit 1.00 = 0.42") == 2

    def test_modifier_out_of_range_is_user_facing_error(self) -> None:
        result = runner.invoke(
            app,
            [
                "estimate",
                "--spec-clarity",
                "0.2",
                "Add login button",
            ],
        )
        assert result.exit_code != 0
        assert "Estimation error:" in result.output
        assert "spec_clarity must be between 0.3 and 1.3" in result.output

    def test_estimate_help_includes_modifier_flags(self) -> None:
        result = runner.invoke(app, ["estimate", "--help"])
        assert result.exit_code == 0
        normalized = _ANSI_ESCAPE_RE.sub("", result.output)
        compact = re.sub(r"\s+", "", normalized)
        assert "--spec-clarity" in compact
        assert "--warm-context" in compact
        assert "--agent-fit" in compact
        assert "0.3to1.3" in compact
        assert "0.3to1.15" in compact
        assert "0.9to1.2" in compact


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

    def test_format_json(self) -> None:
        import json

        result = runner.invoke(app, ["estimate", "--format", "json", "Add button"])
        if result.exit_code == 0:
            # JSON renderer is available — validate parseable JSON output
            data = json.loads(result.output)
            assert isinstance(data, dict)
        else:
            # JSON renderer not yet wired — expect graceful not-implemented message
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
