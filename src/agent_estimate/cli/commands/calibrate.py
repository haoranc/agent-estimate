"""Calibrate command — update and display calibration data."""

from __future__ import annotations

from pathlib import Path

import typer

from agent_estimate.adapters.sqlite_store import SQLiteCalibrationStore

_DEFAULT_DB = Path.home() / ".agent-estimate" / "calibration.db"


def run(
    db: Path = typer.Option(
        _DEFAULT_DB,
        "--db",
        help="Path to calibration database.",
    ),
    basis: str | None = typer.Option(
        None, "--basis",
        help="For legacy DB v1, attest that all stored estimates are expected-work, never caps.",
    ),
) -> None:
    """Update model calibration from historical outcomes."""
    if not db.exists():
        typer.echo("Error: No calibration database found.", err=True)
        typer.echo(f"Expected: {db}", err=True)
        raise typer.Exit(code=2)

    if basis is None:
        typer.echo(
            "Calibration excluded: DB v1 has no forecast-basis provenance. "
            "After verifying every row contains expected work (never caps), "
            "use --basis expected-work.",
            err=True,
        )
        raise typer.Exit(code=2)
    if basis != "expected-work":
        typer.echo("Error: DB v1 only supports expected-work; cap-based scoring is excluded.", err=True)
        raise typer.Exit(code=2)

    typer.echo("Basis: expected-work | source: caller-attested legacy DB v1 | as_of: unknown")
    try:
        with SQLiteCalibrationStore(db) as store:
            store.calibrate()
            rows = store.query_calibration_summary()
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not rows:
        typer.echo("No calibration data available.")
        return

    # Print summary table
    headers = list(rows[0].keys())
    col_widths = {
        h: max(len(h), max(len(str(r.get(h, ""))) for r in rows))
        for h in headers
    }

    header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
    separator = "-+-".join("-" * col_widths[h] for h in headers)
    typer.echo(header_line)
    typer.echo(separator)
    for row in rows:
        line = " | ".join(
            str(row.get(h, "")).ljust(col_widths[h]) for h in headers
        )
        typer.echo(line)
