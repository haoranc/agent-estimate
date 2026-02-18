"""Validate command stub."""

import typer


def run(path: str = typer.Argument(..., help="Path to a task/spec file to validate.")) -> None:
    """Validate estimation input data."""
    typer.echo(f"[stub] validate: {path}")
