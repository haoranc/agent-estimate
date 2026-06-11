"""Shared CLI command helpers."""

from __future__ import annotations

import typer


def validate_output_format(value: str) -> None:
    """Validate a command's output format before side-effectful work runs."""
    if value not in {"markdown", "json"}:
        typer.echo(f"Error: Unknown format: {value!r}. Use markdown or json.", err=True)
        raise typer.Exit(code=2)
