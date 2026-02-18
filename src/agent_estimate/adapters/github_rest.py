"""GitHub REST API adapter for issue ingestion."""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_estimate.adapters.github_adapter import (
    GitHubAdapterError,
    GitHubIssue,
    build_task_description,
)

BASE_URL = "https://api.github.com"


class GitHubRestAdapter:
    """Fetch GitHub issues through the REST API."""

    def __init__(
        self,
        token: str | None = None,
        *,
        max_retries: int = 3,
        initial_backoff_seconds: float = 1.0,
        timeout_seconds: float = 15.0,
        request_fn: Callable[[str, Mapping[str, str]], tuple[int, dict[str, str], str]] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], float] = time.time,
        token_provider: Callable[[], str] | None = None,
    ) -> None:
        self._token = token or (token_provider or _resolve_github_token)()
        self._max_retries = max_retries
        self._initial_backoff_seconds = initial_backoff_seconds
        self._timeout_seconds = timeout_seconds
        self._request_fn = request_fn or self._default_request
        self._sleep_fn = sleep_fn
        self._now_fn = now_fn

    def fetch_issues_by_numbers(self, repo: str, issue_numbers: Sequence[int]) -> list[GitHubIssue]:
        """Fetch specific issues by number."""
        issues: list[GitHubIssue] = []
        for issue_number in issue_numbers:
            payload, _ = self._request_json(
                f"{BASE_URL}/repos/{repo}/issues/{issue_number}",
            )
            if not isinstance(payload, dict):
                raise GitHubAdapterError(f"Unexpected payload for issue #{issue_number}: {payload!r}")
            if "pull_request" in payload:
                continue
            issues.append(_parse_issue(payload))
        return issues

    def fetch_issues_by_label(
        self,
        repo: str,
        label: str,
        *,
        state: str = "open",
    ) -> list[GitHubIssue]:
        """Fetch issues by label, handling paginated API responses."""
        issues: list[GitHubIssue] = []
        page = 1
        while True:
            query = urlencode({"state": state, "labels": label, "per_page": 100, "page": page})
            payload, _ = self._request_json(f"{BASE_URL}/repos/{repo}/issues?{query}")
            if not isinstance(payload, list):
                raise GitHubAdapterError(
                    f"Unexpected payload when listing issues by label '{label}': {payload!r}",
                )
            if not payload:
                break
            for raw_issue in payload:
                if isinstance(raw_issue, dict) and "pull_request" not in raw_issue:
                    issues.append(_parse_issue(raw_issue))
            if len(payload) < 100:
                break
            page += 1
        return issues

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

    def _request_json(self, url: str) -> tuple[object, dict[str, str]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "agent-estimate",
        }

        for attempt in range(self._max_retries + 1):
            status, response_headers, body = self._request_fn(url, headers)
            normalized_headers = {key.lower(): value for key, value in response_headers.items()}

            if status < 400:
                return json.loads(body), normalized_headers

            if _is_rate_limited(status, normalized_headers) and attempt < self._max_retries:
                self._sleep_fn(
                    _compute_retry_delay(
                        headers=normalized_headers,
                        attempt=attempt,
                        initial_backoff_seconds=self._initial_backoff_seconds,
                        now_seconds=self._now_fn(),
                    ),
                )
                continue

            raise GitHubAdapterError(
                f"GitHub API request failed with status {status} for {url}: {body[:200]}",
            )

        raise GitHubAdapterError(f"GitHub API request failed after retries for {url}")

    def _default_request(self, url: str, headers: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
        request = Request(url=url, headers=dict(headers), method="GET")
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.status, dict(response.headers.items()), response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, dict(exc.headers.items()) if exc.headers else {}, body


def _resolve_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token

    result = subprocess.run(
        ["gh", "auth", "token"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        message = result.stderr.strip() or "gh auth token returned no token"
        raise GitHubAdapterError(
            "GitHub authentication required. Set GITHUB_TOKEN or login with gh CLI. "
            f"Details: {message}",
        )
    return result.stdout.strip()


def _parse_issue(raw_issue: Mapping[str, object]) -> GitHubIssue:
    number = int(raw_issue["number"])
    title = str(raw_issue.get("title", ""))
    body = str(raw_issue.get("body") or "")
    return GitHubIssue(
        number=number,
        title=title,
        body=body,
        task_description=build_task_description(title=title, body=body),
    )


def _is_rate_limited(status: int, headers: Mapping[str, str]) -> bool:
    if status == 429:
        return True
    return status == 403 and headers.get("x-ratelimit-remaining") == "0"


def _compute_retry_delay(
    *,
    headers: Mapping[str, str],
    attempt: int,
    initial_backoff_seconds: float,
    now_seconds: float,
) -> float:
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            pass

    reset_epoch = headers.get("x-ratelimit-reset")
    if reset_epoch:
        try:
            return max(float(reset_epoch) - now_seconds, 1.0)
        except ValueError:
            pass

    return max(initial_backoff_seconds * (2**attempt), 1.0)
