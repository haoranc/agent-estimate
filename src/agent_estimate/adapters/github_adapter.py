"""Shared types and interface for GitHub issue adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class GitHubAdapterError(RuntimeError):
    """Raised when issue retrieval from GitHub fails."""


@dataclass(frozen=True)
class GitHubIssue:
    """Normalized issue payload used by estimators."""

    number: int
    title: str
    body: str
    task_description: str


def build_task_description(title: str, body: str | None) -> str:
    """Build one task description from issue title and body text."""
    trimmed_title = title.strip()
    trimmed_body = (body or "").strip()
    if not trimmed_body:
        return trimmed_title
    return f"{trimmed_title}\n\n{trimmed_body}"


class GitHubIssueAdapter(Protocol):
    """Swappable issue adapter interface."""

    def fetch_issues_by_numbers(self, repo: str, issue_numbers: Sequence[int]) -> list[GitHubIssue]:
        """Fetch specific issues by number."""

    def fetch_issues_by_label(
        self,
        repo: str,
        label: str,
        *,
        state: str = "open",
    ) -> list[GitHubIssue]:
        """Fetch issues by label with repository-specific filtering."""

    def fetch_task_descriptions_by_numbers(
        self,
        repo: str,
        issue_numbers: Sequence[int],
    ) -> list[str]:
        """Fetch and transform issue data into estimation task descriptions."""

    def fetch_task_descriptions_by_label(
        self,
        repo: str,
        label: str,
        *,
        state: str = "open",
    ) -> list[str]:
        """Fetch labeled issues and transform them into task descriptions."""
