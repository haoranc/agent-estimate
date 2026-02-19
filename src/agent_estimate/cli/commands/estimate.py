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
from agent_estimate.core.history import infer_warm_context
from agent_estimate.render import render_json_report, render_markdown_report

logger = logging.getLogger("agent_estimate")


def run(
    task: Optional[str] = typer.Argument(None, help="Task description to estimate."),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Path to a task file (one task per line)."
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
    history_file: Optional[Path] = typer.Option(
        None,
        "--history-file",
        help="Dispatch history JSON for auto warm-context detection.",
    ),
    history_agent: Optional[str] = typer.Option(
        None,
        "--history-agent",
        help="Filter dispatch history by agent name.",
    ),
    history_project: Optional[str] = typer.Option(
        None,
        "--history-project",
        help="Filter dispatch history by project name.",
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
            lines = file.read_text(encoding="utf-8").splitlines()
            descriptions = [ln.strip() for ln in lines if ln.strip()]
        except FileNotFoundError:
            _error(f"File not found: {file}", 2)
        if not descriptions:
            _error(f"No task descriptions found in {file}.", 2)
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

    # --- Infer warm context from dispatch history ---
    history_path = history_file
    if history_path is None:
        default_history = Path("data.json")
        if default_history.exists():
            history_path = default_history

    warm_ctx = infer_warm_context(
        history_path, agent=history_agent, project=history_project
    )
    if warm_ctx.value != 1.0:
        logger.info(
            "warm_context: %.2f (auto: %s)", warm_ctx.value, warm_ctx.detail
        )

    # --- Run pipeline ---
    try:
        report = run_estimate_pipeline(
            descriptions,
            cfg,
            review_mode=mode,
            title=title,
            warm_context=warm_ctx.value,
            warm_context_detail=warm_ctx.detail,
        )
    except ValueError as exc:
        _error(f"Estimation error: {exc}", 2)
    except RuntimeError as exc:
        _error(f"Runtime error: {exc}", 1)

    # --- Output ---
    if format == "markdown":
        typer.echo(render_markdown_report(report))
    elif format == "json":
        typer.echo(render_json_report(report), nl=False)
    else:
        _error(f"Unknown format: {format!r}. Use markdown or json.", 2)


def _error(message: str, exit_code: int) -> NoReturn:
    """Print error to stderr and exit."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=exit_code)
