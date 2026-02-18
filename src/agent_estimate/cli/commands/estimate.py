"""Estimate command stub."""

import typer


def run(task: str = typer.Argument(..., help="Task description to estimate.")) -> None:
    """Estimate effort for a task description."""
    typer.echo(f"[stub] estimate: {task}")
