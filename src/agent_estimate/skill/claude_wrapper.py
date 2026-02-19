"""Claude Code skill wrapper — thin adapter for programmatic CLI invocation."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _build_base_cmd(subcommand: str) -> list[str]:
    """Build the base CLI command, preferring the installed binary."""
    binary = shutil.which("agent-estimate")
    if binary:
        return [binary, subcommand]
    return [sys.executable, "-m", "agent_estimate.cli.app", subcommand]


def run_estimate(
    task: str | None = None,
    file: Path | None = None,
    config: Path | None = None,
    format: str = "markdown",
    review_mode: str = "2x-lgtm",
    issues: str | None = None,
    repo: str | None = None,
    title: str = "Agent Estimate Report",
) -> subprocess.CompletedProcess[str]:
    """Invoke ``agent-estimate estimate`` programmatically.

    Returns the completed process so callers can inspect stdout/stderr.
    Raises ``ValueError`` if no input source is provided.
    """
    sources = sum([task is not None, file is not None, issues is not None])
    if sources == 0:
        raise ValueError("Provide task, file, or issues.")
    if sources > 1:
        raise ValueError("Provide only one input source: task, file, or issues.")

    cmd: list[str] = _build_base_cmd("estimate")

    if task is not None:
        cmd.append(task)
    if file is not None:
        cmd += ["--file", str(file)]
    if config is not None:
        cmd += ["--config", str(config)]
    if format != "markdown":
        cmd += ["--format", format]
    if review_mode != "2x-lgtm":
        cmd += ["--review-mode", review_mode]
    if issues is not None:
        cmd += ["--issues", issues]
    if repo is not None:
        cmd += ["--repo", repo]
    if title != "Agent Estimate Report":
        cmd += ["--title", title]

    return subprocess.run(cmd, capture_output=True, text=True)


def run_validate(
    observation_file: Path,
    db: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke ``agent-estimate validate`` programmatically."""
    cmd: list[str] = _build_base_cmd("validate")
    cmd.append(str(observation_file))
    if db is not None:
        cmd += ["--db", str(db)]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_calibrate(db: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke ``agent-estimate calibrate`` programmatically."""
    cmd: list[str] = _build_base_cmd("calibrate")
    if db is not None:
        cmd += ["--db", str(db)]
    return subprocess.run(cmd, capture_output=True, text=True)
