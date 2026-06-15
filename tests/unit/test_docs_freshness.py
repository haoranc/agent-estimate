"""Docs freshness guards (#28).

README's hero example and examples/multi-agent.md embed captured CLI output.
These tests re-run the same estimate and assert the embedded headline lines
still match what the tool actually prints, so a prior recalibration or METR
model-key bump fails CI instead of silently rotting the docs.
"""

from pathlib import Path

from typer.testing import CliRunner

from agent_estimate.cli.app import app

ROOT = Path(__file__).resolve().parents[2]

# The documented input from examples/multi-agent.md "Input file" block.
MULTI_AGENT_TASKS = [
    "Implement add-agent CLI command with SPEC.md generation",
    "Add known_debt.md as standard protocol memory file",
    "Write quickstart guide with protocol comparison table",
]

# Headline output lines embedded verbatim in README.md and
# examples/multi-agent.md. If the CLI stops producing them, both docs
# need re-capturing.
HEADLINE_LINES = [
    "| Expected case | 75.4m |",
    "| Compression ratio | 8.07x |",
    "exceeds gpt_5_4 p80 threshold (60m)",
    "exceeds gemini_3_1_pro p80 threshold (45m)",
]

runner = CliRunner()


def _real_output(tmp_path: Path) -> str:
    task_file = tmp_path / "tasks.txt"
    task_file.write_text("\n".join(MULTI_AGENT_TASKS) + "\n", encoding="utf-8")
    result = runner.invoke(app, ["estimate", "--file", str(task_file)])
    assert result.exit_code == 0, result.output
    return result.output


class TestDocsFreshness:
    def test_example_input_block_lists_the_tasks(self):
        example = (ROOT / "examples" / "multi-agent.md").read_text()
        for task in MULTI_AGENT_TASKS:
            assert task in example, f"examples/multi-agent.md lost input task {task!r}"

    def test_readme_hero_matches_real_run(self, tmp_path):
        output = _real_output(tmp_path)
        readme = (ROOT / "README.md").read_text()
        for line in HEADLINE_LINES:
            assert line in output, (
                f"CLI no longer prints {line!r} for the documented tasks — "
                "re-capture the README hero block and examples/multi-agent.md"
            )
            assert line in readme, f"README hero block lost {line!r}"

    def test_example_output_matches_real_run(self, tmp_path):
        output = _real_output(tmp_path)
        example = (ROOT / "examples" / "multi-agent.md").read_text()
        for line in HEADLINE_LINES:
            assert line in output
            assert line in example, f"examples/multi-agent.md output block lost {line!r}"

    def test_session_command_is_documented_outside_changelog(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "agent-estimate session" in readme

    def test_release_checklist_mentions_floating_v0_action_tag(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        assert "floating public Action tag" in contributing
        assert "git tag -f v0" in contributing
