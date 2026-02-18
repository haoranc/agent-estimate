"""GitHub CLI adapter fallback for issue ingestion."""

from __future__ import annotations

import json
import subprocess
from typing import Callable, Sequence

from agent_estimate.adapters.github_adapter import (
    GitHubAdapterError,
    GitHubIssue,
    build_task_description,
)


class GitHubGhCliAdapter:
    """Fetch GitHub issues through gh CLI commands."""

    def __init__(self, runner: Callable[[list[str]], str] | None = None) -> None:
        self._runner = runner or _run_gh

    def fetch_issues_by_numbers(self, repo: str, issue_numbers: Sequence[int]) -> list[GitHubIssue]:
        """Fetch specific issues by number."""
        issues: list[GitHubIssue] = []
        for issue_number in issue_numbers:
            output = self._runner(
                [
                    "gh",
                    "issue",
                    "view",
                    str(issue_number),
                    "--repo",
                    repo,
                    "--json",
                    "number,title,body",
                ],
            )
            payload = json.loads(output)
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
        output = self._runner(
            [
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
                "1000",
                "--json",
                "number,title,body",
            ],
        )
        payload = json.loads(output)
        if not isinstance(payload, list):
            raise GitHubAdapterError(f"Unexpected gh issue list output: {payload!r}")
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
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitHubAdapterError(
            f"gh command failed ({' '.join(args)}): {result.stderr.strip() or result.stdout.strip()}",
        )
    return result.stdout


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
