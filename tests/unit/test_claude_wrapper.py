"""Tests for the Claude skill subprocess wrapper."""

from __future__ import annotations

import subprocess

from agent_estimate.skill import claude_wrapper


def test_run_estimate_default_review_mode_is_standard(
    monkeypatch,
) -> None:
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(claude_wrapper.shutil, "which", lambda _: "agent-estimate")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(claude_wrapper.subprocess, "run", fake_run)

    claude_wrapper.run_estimate(task="Add tests")

    assert captured["cmd"] == ["agent-estimate", "estimate", "Add tests"]


def test_run_estimate_custom_review_mode_is_forwarded(
    monkeypatch,
) -> None:
    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(claude_wrapper.shutil, "which", lambda _: "agent-estimate")

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(claude_wrapper.subprocess, "run", fake_run)

    claude_wrapper.run_estimate(task="Add tests", review_mode="complex")

    assert captured["cmd"] == [
        "agent-estimate",
        "estimate",
        "Add tests",
        "--review-mode",
        "complex",
    ]
