"""Unit tests for GitHub issue adapters."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping

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
