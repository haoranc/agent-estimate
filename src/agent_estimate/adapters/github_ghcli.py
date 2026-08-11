"""GitHub CLI adapter fallback for issue ingestion."""

from __future__ import annotations

import json
import subprocess
import time
import warnings
from collections.abc import Callable, Sequence

from agent_estimate.adapters.github_adapter import (
    GitHubAdapterError,
    GitHubIssue,
    build_task_description,
)
from agent_estimate.audit import emit_audit_event

_ISSUE_LIST_LIMIT = 1000


class GitHubGhCliAdapter:
    """Fetch GitHub issues through gh CLI commands."""

    def __init__(self, runner: Callable[[list[str]], str] | None = None) -> None:
        self._runner = runner or _run_gh

    def fetch_issues_by_numbers(self, repo: str, issue_numbers: Sequence[int]) -> list[GitHubIssue]:
        """Fetch specific issues by number."""
        issues: list[GitHubIssue] = []
        for issue_number in issue_numbers:
            args = [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--repo",
                repo,
                "--json",
                "number,title,body",
            ]
            started_at = time.perf_counter()
            try:
                output = self._runner(args)
            except Exception as exc:
                emit_audit_event(
                    "api_call",
                    action="github_issue_view",
                    outcome="error",
                    duration_ms=(time.perf_counter() - started_at) * 1000.0,
                    client="gh",
                    endpoint="gh issue view",
                    repo=repo,
                    issue_number=issue_number,
                    error_type=type(exc).__name__,
                )
                raise
            emit_audit_event(
                "api_call",
                action="github_issue_view",
                duration_ms=(time.perf_counter() - started_at) * 1000.0,
                client="gh",
                endpoint="gh issue view",
                repo=repo,
                issue_number=issue_number,
            )
            payload = _load_json(output, "gh issue view")
            if not isinstance(payload, dict):
                raise GitHubAdapterError(f"Unexpected gh issue view output: {payload!r}")
            issues.append(_parse_issue(payload))
        return issues

    def fetch_issues_by_label(
        self,
        repo: str,
        label: str,
        *,
        state: str = "open",
    ) -> list[GitHubIssue]:
        """Fetch issues by label with a high limit for CLI pagination fallback."""
        args = [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            label,
            "--state",
            state,
            "--limit",
            str(_ISSUE_LIST_LIMIT),
            "--json",
            "number,title,body",
        ]
        started_at = time.perf_counter()
        try:
            output = self._runner(args)
        except Exception as exc:
            emit_audit_event(
                "api_call",
                action="github_issue_list",
                outcome="error",
                duration_ms=(time.perf_counter() - started_at) * 1000.0,
                client="gh",
                endpoint="gh issue list",
                repo=repo,
                label=label,
                state=state,
                error_type=type(exc).__name__,
            )
            raise
        emit_audit_event(
            "api_call",
            action="github_issue_list",
            duration_ms=(time.perf_counter() - started_at) * 1000.0,
            client="gh",
            endpoint="gh issue list",
            repo=repo,
            label=label,
            state=state,
        )
        payload = _load_json(output, "gh issue list")
        if not isinstance(payload, list):
            raise GitHubAdapterError(f"Unexpected gh issue list output: {payload!r}")
        if len(payload) >= _ISSUE_LIST_LIMIT:
            warnings.warn(
                "gh issue list returned the 1000-item limit; results may be truncated",
                RuntimeWarning,
                stacklevel=2,
            )
            emit_audit_event(
                "api_call",
                action="github_issue_list",
                outcome="warning",
                level="WARNING",
                client="gh",
                endpoint="gh issue list",
                repo=repo,
                label=label,
                state=state,
                result_count=len(payload),
                limit=_ISSUE_LIST_LIMIT,
            )
        return [_parse_issue(raw_issue) for raw_issue in payload]

    def fetch_task_descriptions_by_numbers(
        self,
        repo: str,
        issue_numbers: Sequence[int],
    ) -> list[str]:
        """Fetch issues by number and return task descriptions."""
        return [issue.task_description for issue in self.fetch_issues_by_numbers(repo, issue_numbers)]

    def fetch_task_descriptions_by_label(
        self,
        repo: str,
        label: str,
        *,
        state: str = "open",
    ) -> list[str]:
        """Fetch labeled issues and return task descriptions."""
        return [issue.task_description for issue in self.fetch_issues_by_label(repo, label, state=state)]


def _run_gh(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise GitHubAdapterError(
            "gh CLI not found; install gh or set GITHUB_TOKEN",
        ) from exc
    if result.returncode != 0:
        raise GitHubAdapterError(
            f"gh command failed ({' '.join(args)}): {result.stderr.strip() or result.stdout.strip()}",
        )
    return result.stdout


def _load_json(output: str, command: str) -> object:
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise GitHubAdapterError(f"{command} returned invalid JSON: {exc}") from exc


def _parse_issue(payload: dict[str, object]) -> GitHubIssue:
    number = int(payload["number"])
    title = str(payload.get("title", ""))
    body = str(payload.get("body") or "")
    return GitHubIssue(
        number=number,
        title=title,
        body=body,
        task_description=build_task_description(title=title, body=body),
    )
