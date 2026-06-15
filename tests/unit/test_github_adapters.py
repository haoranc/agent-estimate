"""Unit tests for GitHub issue adapters."""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

import pytest

from agent_estimate.audit import reset_audit_logger
from agent_estimate.adapters import github_rest
from agent_estimate.adapters.github_adapter import GitHubAdapterError
from agent_estimate.adapters.github_ghcli import GitHubGhCliAdapter
from agent_estimate.adapters.github_rest import GitHubRestAdapter


def test_rest_adapter_fetches_issues_by_number_and_builds_task_descriptions() -> None:
    responses = {
        "https://api.github.com/repos/acme/repo/issues/1": (
            200,
            {},
            json.dumps({"number": 1, "title": "Fix parser", "body": "Handle YAML edge cases"}),
        ),
        "https://api.github.com/repos/acme/repo/issues/2": (
            200,
            {},
            json.dumps({"number": 2, "title": "Write tests", "body": ""}),
        ),
    }

    def request_fn(url: str, headers: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        assert headers["Authorization"] == "Bearer test-token"
        return responses[url]

    adapter = GitHubRestAdapter(token_provider=lambda: "test-token", request_fn=request_fn)
    issues = adapter.fetch_issues_by_numbers("acme/repo", [1, 2])

    assert [issue.number for issue in issues] == [1, 2]
    assert issues[0].task_description == "Fix parser\n\nHandle YAML edge cases"
    assert issues[1].task_description == "Write tests"


def test_rest_adapter_handles_pagination_for_label_queries() -> None:
    first_page = [{"number": i, "title": f"Issue {i}", "body": "Body"} for i in range(1, 101)]
    second_page = [
        {"number": 101, "title": "Issue 101", "body": "Body"},
        {"number": 102, "title": "Issue 102", "body": "Body"},
    ]

    responses = {
        "https://api.github.com/repos/acme/repo/issues?state=open&labels=bug&per_page=100&page=1": (
            200,
            {},
            json.dumps(first_page),
        ),
        "https://api.github.com/repos/acme/repo/issues?state=open&labels=bug&per_page=100&page=2": (
            200,
            {},
            json.dumps(second_page),
        ),
    }

    def request_fn(url: str, _: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        return responses[url]

    adapter = GitHubRestAdapter(token_provider=lambda: "test-token", request_fn=request_fn)
    issues = adapter.fetch_issues_by_label("acme/repo", "bug")

    assert len(issues) == 102
    assert issues[0].number == 1
    assert issues[-1].number == 102


def test_rest_adapter_retries_when_rate_limited() -> None:
    calls = defaultdict(int)
    sleep_calls: list[float] = []

    def request_fn(url: str, _: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        calls[url] += 1
        if calls[url] == 1:
            return (
                403,
                {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "102"},
                '{"message":"rate limited"}',
            )
        return 200, {}, json.dumps({"number": 7, "title": "Retry me", "body": "Worked"})

    adapter = GitHubRestAdapter(
        token_provider=lambda: "test-token",
        request_fn=request_fn,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        now_fn=lambda: 100.0,
    )

    issues = adapter.fetch_issues_by_numbers("acme/repo", [7])

    assert issues[0].number == 7
    assert sleep_calls == [2.0]


def test_rest_adapter_caps_rate_limit_reset_delay() -> None:
    delay = github_rest._compute_retry_delay(
        headers={"x-ratelimit-reset": "10000"},
        attempt=0,
        initial_backoff_seconds=1.0,
        now_seconds=100.0,
    )

    assert delay == github_rest.MAX_RETRY_DELAY_SECONDS


def test_gh_cli_adapter_fetches_issues_by_number_and_label() -> None:
    def runner(args: list[str]) -> str:
        if args[:3] == ["gh", "issue", "view"]:
            return json.dumps({"number": 9, "title": "CLI title", "body": "CLI body"})
        if args[:3] == ["gh", "issue", "list"]:
            return json.dumps(
                [
                    {"number": 10, "title": "Label title", "body": "Body"},
                    {"number": 11, "title": "Second title", "body": ""},
                ],
            )
        raise AssertionError(f"unexpected args: {args}")

    adapter = GitHubGhCliAdapter(runner=runner)
    by_number = adapter.fetch_task_descriptions_by_numbers("acme/repo", [9])
    by_label = adapter.fetch_task_descriptions_by_label("acme/repo", "estimate")

    assert by_number == ["CLI title\n\nCLI body"]
    assert by_label == ["Label title\n\nBody", "Second title"]


def test_gh_cli_adapter_wraps_invalid_json() -> None:
    adapter = GitHubGhCliAdapter(runner=lambda _: "not-json")

    with pytest.raises(GitHubAdapterError, match="invalid JSON"):
        adapter.fetch_issues_by_numbers("acme/repo", [9])


def test_gh_cli_adapter_wraps_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr("agent_estimate.adapters.github_ghcli.subprocess.run", fake_run)

    adapter = GitHubGhCliAdapter()
    with pytest.raises(GitHubAdapterError, match="gh CLI not found"):
        adapter.fetch_issues_by_numbers("acme/repo", [9])


def test_rest_adapter_wraps_invalid_json_response() -> None:
    adapter = GitHubRestAdapter(
        token_provider=lambda: "test-token",
        request_fn=lambda _url, _headers: (200, {}, "not-json"),
    )

    with pytest.raises(GitHubAdapterError, match="invalid JSON"):
        adapter.fetch_issues_by_numbers("acme/repo", [9])


def test_rest_adapter_emits_auth_and_api_audit_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_ENABLED", "1")
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_DESTINATION", str(audit_log))
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_LEVEL", "INFO")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    reset_audit_logger()

    def request_fn(url: str, headers: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        assert headers["Authorization"] == "Bearer test-token"
        return (
            200,
            {},
            json.dumps({"number": 5, "title": "Audit this", "body": "No secrets"}),
        )

    adapter = GitHubRestAdapter(request_fn=request_fn)
    issues = adapter.fetch_issues_by_numbers("acme/repo", [5])

    reset_audit_logger()
    assert issues[0].number == 5
    raw_log = audit_log.read_text(encoding="utf-8")
    assert "test-token" not in raw_log
    events = [json.loads(line) for line in raw_log.splitlines() if line.strip()]

    auth_event = next(event for event in events if event["event_type"] == "authentication_event")
    assert auth_event["details"]["provider"] == "env"

    api_event = next(event for event in events if event["event_type"] == "api_call")
    assert api_event["details"]["client"] == "github_rest"
    assert api_event["details"]["status_code"] == 200
    assert api_event["details"]["endpoint"].endswith("/repos/acme/repo/issues/5")


def test_gh_cli_adapter_emits_api_audit_event(tmp_path: Path, monkeypatch) -> None:
    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_ENABLED", "1")
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_DESTINATION", str(audit_log))
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_LEVEL", "INFO")
    reset_audit_logger()

    def runner(args: list[str]) -> str:
        assert args[:3] == ["gh", "issue", "view"]
        return json.dumps({"number": 9, "title": "CLI title", "body": "CLI body"})

    adapter = GitHubGhCliAdapter(runner=runner)
    issues = adapter.fetch_issues_by_numbers("acme/repo", [9])

    reset_audit_logger()
    assert issues[0].number == 9
    events = [
        json.loads(line)
        for line in audit_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    api_event = next(event for event in events if event["event_type"] == "api_call")
    assert api_event["details"]["client"] == "gh"
    assert api_event["details"]["endpoint"] == "gh issue view"
    assert api_event["details"]["issue_number"] == 9
    assert "status" not in api_event["details"]


def test_rest_adapter_auth_failure_audit_event_redacts_raw_gh_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    audit_log = tmp_path / "audit.jsonl"
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_ENABLED", "1")
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_DESTINATION", str(audit_log))
    monkeypatch.setenv("AGENT_ESTIMATE_AUDIT_LEVEL", "INFO")
    reset_audit_logger()

    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="gh auth token failed for /Users/testuser/.config/gh/hosts.yml",
        )

    monkeypatch.setattr(github_rest.subprocess, "run", fake_run)

    with pytest.raises(GitHubAdapterError):
        github_rest._resolve_github_token()

    reset_audit_logger()
    raw_log = audit_log.read_text(encoding="utf-8")
    assert "/Users/testuser" not in raw_log
    events = [json.loads(line) for line in raw_log.splitlines() if line.strip()]
    auth_event = next(event for event in events if event["event_type"] == "authentication_event")
    assert auth_event["outcome"] == "error"
    assert auth_event["details"]["error_type"] == "gh_auth_failure"
    assert "error" not in auth_event["details"]


def test_rest_adapter_wraps_missing_gh_token_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(github_rest.subprocess, "run", fake_run)

    with pytest.raises(GitHubAdapterError, match="gh CLI not found"):
        github_rest._resolve_github_token()
