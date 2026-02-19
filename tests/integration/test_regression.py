"""Regression tests — fixed inputs with expected output structure and values."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from agent_estimate.cli.app import app

runner = CliRunner()
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_section(output: str, heading: str) -> str:
    """Extract a markdown section by ## heading (up to the next ## or EOF)."""
    pattern = rf"(## {re.escape(heading)}\n.*?)(?=\n## |\Z)"
    match = re.search(pattern, output, re.DOTALL)
    assert match, f"Section '{heading}' not found in output"
    return match.group(1)


def _count_table_rows(section: str) -> int:
    """Count data rows in a markdown table (exclude header + separator)."""
    lines = [ln for ln in section.strip().splitlines() if ln.startswith("|")]
    # Subtract header row and separator row
    return max(0, len(lines) - 2)


# ---------------------------------------------------------------------------
# Single-task regression with simple_linear config
# ---------------------------------------------------------------------------


class TestSingleTaskSimpleLinear:
    """Regression: one task, one agent (Solo), no friction/overhead."""

    CONFIG = str(FIXTURES / "simple_linear.yaml")
    TASK = "Add login button"

    def _run(self) -> str:
        result = runner.invoke(
            app,
            ["estimate", "--config", self.CONFIG, "--review-mode", "none", self.TASK],
        )
        assert result.exit_code == 0, result.output
        return result.output

    def test_report_title(self) -> None:
        output = self._run()
        assert output.startswith("# Agent Estimate Report")

    def test_has_all_sections(self) -> None:
        output = self._run()
        expected_sections = [
            "Per-Task Estimates",
            "Wave Plan",
            "Timeline Summary",
            "Review Overhead (Additive)",
            "Agent Load Summary",
            "Critical Path",
            "METR Warnings",
        ]
        for section in expected_sections:
            assert f"## {section}" in output, f"Missing section: {section}"

    def test_single_task_row(self) -> None:
        output = self._run()
        section = _extract_section(output, "Per-Task Estimates")
        assert _count_table_rows(section) == 1

    def test_agent_is_solo(self) -> None:
        output = self._run()
        section = _extract_section(output, "Per-Task Estimates")
        assert "Solo" in section

    def test_one_wave(self) -> None:
        output = self._run()
        section = _extract_section(output, "Wave Plan")
        assert _count_table_rows(section) == 1

    def test_review_overhead_zero_for_none_mode(self) -> None:
        output = self._run()
        section = _extract_section(output, "Review Overhead (Additive)")
        # The total review overhead should be 0m for review_mode=none
        assert "0m" in section

    def test_timeline_values_positive(self) -> None:
        output = self._run()
        section = _extract_section(output, "Timeline Summary")
        # Extract numeric minute values from the timeline table
        values = re.findall(r"(\d+(?:\.\d+)?)m", section)
        assert len(values) >= 3, "Expected at least best/expected/worst values"
        for val in values[:3]:
            assert float(val) > 0

    def test_agent_load_shows_solo(self) -> None:
        output = self._run()
        section = _extract_section(output, "Agent Load Summary")
        assert "Solo" in section
        assert _count_table_rows(section) == 1


# ---------------------------------------------------------------------------
# Multi-task regression with parallel_fanout config
# ---------------------------------------------------------------------------


class TestMultiTaskParallelFanout:
    """Regression: 3 tasks, 2 agents (Alpha + Beta), friction + overhead."""

    CONFIG = str(FIXTURES / "parallel_fanout.yaml")
    TASK_FILE = str(FIXTURES / "tasks_multi.txt")

    def _run(self) -> str:
        result = runner.invoke(
            app,
            ["estimate", "--config", self.CONFIG, "--file", self.TASK_FILE],
        )
        assert result.exit_code == 0, result.output
        return result.output

    def test_three_task_rows(self) -> None:
        output = self._run()
        section = _extract_section(output, "Per-Task Estimates")
        assert _count_table_rows(section) == 3

    def test_both_agents_appear(self) -> None:
        output = self._run()
        section = _extract_section(output, "Agent Load Summary")
        assert "Alpha" in section
        assert "Beta" in section

    def test_agent_load_has_two_rows(self) -> None:
        output = self._run()
        section = _extract_section(output, "Agent Load Summary")
        assert _count_table_rows(section) == 2

    def test_compression_ratio_present(self) -> None:
        output = self._run()
        section = _extract_section(output, "Timeline Summary")
        assert "Compression ratio" in section
        match = re.search(r"(\d+\.\d+)x", section)
        assert match, "Compression ratio value not found"

    def test_review_overhead_positive_for_default_mode(self) -> None:
        output = self._run()
        # Default review mode is 2x-lgtm, so overhead should be > 0
        section = _extract_section(output, "Review Overhead (Additive)")
        total_line = [ln for ln in section.splitlines() if "**Total**" in ln]
        assert len(total_line) == 1
        match = re.search(r"(\d+(?:\.\d+)?)m", total_line[0])
        assert match
        assert float(match.group(1)) > 0

    def test_critical_path_present(self) -> None:
        output = self._run()
        section = _extract_section(output, "Critical Path")
        # Should contain at least one bold task name
        assert "**" in section


# ---------------------------------------------------------------------------
# Determinism: same inputs produce same output
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Regression: identical inputs must produce identical output."""

    CONFIG = str(FIXTURES / "simple_linear.yaml")
    TASK = "Refactor payment module"

    def test_two_runs_identical(self) -> None:
        result1 = runner.invoke(
            app,
            ["estimate", "--config", self.CONFIG, "--review-mode", "self", self.TASK],
        )
        result2 = runner.invoke(
            app,
            ["estimate", "--config", self.CONFIG, "--review-mode", "self", self.TASK],
        )
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert result1.output == result2.output


# ---------------------------------------------------------------------------
# Validate regression
# ---------------------------------------------------------------------------


class TestValidateRegression:
    """Regression: validate command output structure."""

    OBS = str(FIXTURES / "observation_valid.yaml")

    def test_output_structure(self) -> None:
        result = runner.invoke(app, ["validate", self.OBS])
        assert result.exit_code == 0
        output = result.output
        assert "Estimation vs Actual Comparison" in output
        assert "Estimated:" in output
        assert "Actual (work):" in output
        assert "Actual (total):" in output
        assert "Error ratio:" in output
        assert "Verdict:" in output

    def test_accurate_verdict_for_fixture(self) -> None:
        result = runner.invoke(app, ["validate", self.OBS])
        assert result.exit_code == 0
        # 25/30 = 0.833 which is between 0.8 and 1.2 => ACCURATE
        assert "ACCURATE" in result.output

    def test_estimated_value(self) -> None:
        result = runner.invoke(app, ["validate", self.OBS])
        assert result.exit_code == 0
        assert "30.0 min" in result.output

    def test_actual_work_value(self) -> None:
        result = runner.invoke(app, ["validate", self.OBS])
        assert result.exit_code == 0
        assert "25.0 min" in result.output
