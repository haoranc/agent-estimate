"""Executed tests for the GitHub Action's shell runtime helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WRITE_OUTPUT = ROOT / "scripts" / "write_github_output.sh"
UPSERT_COMMENT = ROOT / "scripts" / "upsert_action_comment.sh"
MARKER = "<!-- agent-estimate:forecast -->"


def test_write_github_output_preserves_delimiter_containing_value(tmp_path: Path) -> None:
    output_path = tmp_path / "github-output"
    value = "Delimiter regression\nAE_EOF\nreport body"
    env = os.environ.copy()
    env["GITHUB_OUTPUT"] = str(output_path)

    subprocess.run(
        ["bash", str(WRITE_OUTPUT), "report"],
        input=value,
        text=True,
        check=True,
        env=env,
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    name, delimiter = lines[0].split("<<", 1)
    assert name == "report"
    assert delimiter != "AE_EOF"
    assert delimiter not in value.splitlines()
    assert lines[1:-1] == value.splitlines()
    assert lines[-1] == delimiter


def _install_fake_gh(tmp_path: Path) -> tuple[Path, Path]:
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "calls.jsonl"
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["FAKE_GH_STATE"])
log_path = Path(os.environ["FAKE_GH_LOG"])
args = sys.argv[1:]
with log_path.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\\n")

state = json.loads(state_path.read_text()) if state_path.exists() else {}
if args[:2] == ["api", "--paginate"]:
    jq_filter = args[args.index("--jq") + 1]
    if '.user.type == "Bot"' not in jq_filter:
        raise SystemExit("marker search must be bot-author constrained")
    if state.get("comment_id") and state.get("comment_author_type", "Bot") == "Bot":
        print(state["comment_id"])
elif args[:3] == ["api", "--method", "PATCH"]:
    state["patches"] = state.get("patches", 0) + 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
elif len(args) >= 2 and args[0] in {"issue", "pr"} and args[1] == "comment":
    state["comment_id"] = 123
    state["creates"] = state.get("creates", 0) + 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
else:
    raise SystemExit(f"unexpected fake gh invocation: {args}")
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    return state_path, log_path


@pytest.mark.parametrize("kind", ["issue", "pr"])
def test_upsert_comment_creates_once_then_updates_marker(
    tmp_path: Path, kind: str
) -> None:
    state_path, log_path = _install_fake_gh(tmp_path)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env["FAKE_GH_STATE"] = str(state_path)
    env["FAKE_GH_LOG"] = str(log_path)

    for body in ("first report", "replacement report"):
        subprocess.run(
            ["bash", str(UPSERT_COMMENT), kind, "17", "owner/repo"],
            input=body,
            text=True,
            check=True,
            env=env,
        )

    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    create_calls = [call for call in calls if call[:2] == [kind, "comment"]]
    patch_calls = [call for call in calls if call[:3] == ["api", "--method", "PATCH"]]
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert state == {"comment_id": 123, "creates": 1, "patches": 1}
    assert len(create_calls) == 1
    assert len(patch_calls) == 1
    assert MARKER in create_calls[0][create_calls[0].index("--body") + 1]
    raw_body = patch_calls[0][patch_calls[0].index("--raw-field") + 1]
    assert raw_body.startswith(f"body={MARKER}\n\n")
    assert raw_body.endswith("replacement report")


def test_upsert_comment_does_not_edit_human_marker(tmp_path: Path) -> None:
    state_path, log_path = _install_fake_gh(tmp_path)
    state_path.write_text(
        json.dumps({"comment_id": 321, "comment_author_type": "User"}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    env["FAKE_GH_STATE"] = str(state_path)
    env["FAKE_GH_LOG"] = str(log_path)

    subprocess.run(
        ["bash", str(UPSERT_COMMENT), "issue", "17", "owner/repo"],
        input="replacement report",
        text=True,
        check=True,
        env=env,
    )

    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert not any(call[:3] == ["api", "--method", "PATCH"] for call in calls)
    assert sum(call[:2] == ["issue", "comment"] for call in calls) == 1


def test_action_permission_descriptions_match_readme() -> None:
    metadata = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    description = metadata["inputs"]["output-mode"]["description"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for requirement in (
        "issues: read",
        "pull-requests: write",
        "issues: write",
        "contents: read",
    ):
        assert requirement in description
        assert requirement in readme

    assert (
        "| `pr-comment` | `issues: read` when issue input comes from a private "
        "repository, plus `pull-requests: write` |"
    ) in readme
    assert (
        "| pr-comment | issues: read for private-repo issue input, plus "
        "pull-requests: write |"
    ) in description

    action_text = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "report<<AE_EOF" not in action_text
    assert "AE_BODY_EOF" not in action_text
    assert "write_github_output.sh" in action_text
    assert "upsert_action_comment.sh" in action_text
