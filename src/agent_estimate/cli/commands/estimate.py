"""Estimate command — full pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NoReturn, Optional

import typer

from agent_estimate.adapters.config_loader import load_config, load_default_config
from agent_estimate.adapters.github_adapter import GitHubAdapterError
from agent_estimate.adapters.github_ghcli import GitHubGhCliAdapter
from agent_estimate.cli.commands._pipeline import run_estimate_pipeline
from agent_estimate.cli.commands.github import parse_issue_selection
from agent_estimate.core import ReviewMode
from agent_estimate.render import render_markdown_report

logger = logging.getLogger("agent_estimate")


def run(
    task: Optional[str] = typer.Argument(None, help="Task description to estimate."),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to a spec/task file."
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to config YAML."
    ),
    format: str = typer.Option(
        "markdown", "--format", help="Output format: markdown or json."
    ),
    review_mode: str = typer.Option(
        "2x-lgtm", "--review-mode", help="Review mode: none, self, 2x-lgtm."
    ),
    issues: Optional[str] = typer.Option(
        None, "--issues", "-i", help="Comma-separated GitHub issue numbers."
    ),
    repo: Optional[str] = typer.Option(
        None, "--repo", "-r", help="GitHub repo (owner/name)."
    ),
    title: str = typer.Option(
        "Agent Estimate Report", "--title", "-t", help="Report title."
    ),
) -> None:
    """Estimate effort for one or more task descriptions."""
    # --- Resolve input source (exactly one) ---
    sources = sum([task is not None, file is not None, issues is not None])
    if sources == 0:
        _error("Provide a task description, --file, or --issues.", 2)
    if sources > 1:
        _error("Provide only one input source: task argument, --file, or --issues.", 2)

    descriptions: list[str] = []

    if task is not None:
        descriptions = [task]
    elif file is not None:
        try:
            descriptions = [file.read_text(encoding="utf-8")]
        except FileNotFoundError:
            _error(f"File not found: {file}", 2)
    elif issues is not None:
        if not repo:
            _error("--repo is required when using --issues.", 2)
        try:
            issue_numbers = parse_issue_selection(issues)
        except ValueError:
            _error(f"Invalid issue numbers: {issues}", 2)
        if not issue_numbers:
            _error("No issue numbers provided.", 2)
        try:
            adapter = GitHubGhCliAdapter()
            descriptions = adapter.fetch_task_descriptions_by_numbers(
                repo, issue_numbers
            )
        except GitHubAdapterError as exc:
            _error(f"GitHub error: {exc}", 1)

    # --- Resolve review mode ---
    try:
        mode = ReviewMode(review_mode)
    except ValueError:
        _error(
            f"Invalid review mode: {review_mode!r}. Use none, self, or 2x-lgtm.", 2
        )

    # --- Load config ---
    try:
        cfg = load_config(config) if config else load_default_config()
    except FileNotFoundError:
        _error(f"Config file not found: {config}", 2)
    except ValueError as exc:
        _error(f"Config validation error: {exc}", 2)

    # --- Run pipeline ---
    try:
        report = run_estimate_pipeline(
            descriptions, cfg, review_mode=mode, title=title
        )
    except ValueError as exc:
        _error(f"Estimation error: {exc}", 2)
    except RuntimeError as exc:
        _error(f"Runtime error: {exc}", 1)

    # --- Output ---
    if format == "markdown":
        typer.echo(render_markdown_report(report))
    elif format == "json":
        _error("JSON output not yet implemented.", 1)
    else:
        _error(f"Unknown format: {format!r}. Use markdown or json.", 2)


def _error(message: str, exit_code: int) -> NoReturn:
    """Print error to stderr and exit."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=exit_code)
