"""Validate command — compare estimation against observed outcomes."""

from __future__ import annotations

import math
from pathlib import Path

import typer
import yaml

from agent_estimate.adapters.sqlite_store import ObservationInput, SQLiteCalibrationStore
from agent_estimate.contract.duration import resolve_scoring_basis


def run(
    observation_file: Path = typer.Argument(
        ..., help="Path to observation YAML file."
    ),
    db: Path | None = typer.Option(
        None, "--db", help="Path to calibration database to store observation."
    ),
) -> None:
    """Compare an estimation against actual observed outcomes."""
    if not observation_file.exists():
        typer.echo(f"Error: File not found: {observation_file}", err=True)
        raise typer.Exit(code=2)

    try:
        raw = yaml.safe_load(observation_file.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Error: Failed to parse YAML: {exc}", err=True)
        raise typer.Exit(code=2)

    if not isinstance(raw, dict):
        typer.echo("Error: Observation file must be a YAML mapping.", err=True)
        raise typer.Exit(code=2)

    # Extract required fields
    try:
        estimated, basis = resolve_scoring_basis(raw)
        if basis == "expected-wall" and "actual_total_minutes" not in raw:
            raise ValueError("expected-wall scoring requires actual_total_minutes")
        actual_work = float(raw["actual_work_minutes"])
        actual_total = float(raw.get("actual_total_minutes", actual_work))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        typer.echo(f"Error: Missing or invalid field: {exc}", err=True)
        raise typer.Exit(code=2)

    for name, value in (
        ("estimated_minutes", estimated),
        ("actual_work_minutes", actual_work),
        ("actual_total_minutes", actual_total),
    ):
        if not math.isfinite(value):
            typer.echo(f"Error: {name} must be finite", err=True)
            raise typer.Exit(code=2)

    if estimated <= 0:
        typer.echo("Error: estimated_minutes must be > 0", err=True)
        raise typer.Exit(code=2)
    if actual_work < 0:
        typer.echo("Error: actual_work_minutes must be >= 0", err=True)
        raise typer.Exit(code=2)
    if actual_total < actual_work:
        typer.echo("Error: actual_total_minutes must be >= actual_work_minutes", err=True)
        raise typer.Exit(code=2)

    # Store v1 records expected work only and cannot retain wall-basis provenance.
    # Refuse mixed-basis persistence until the separately scoped store-v2 leg.
    if db is not None and basis != "expected-work":
        typer.echo("Error: calibration DB v1 accepts expected-work only; wall scoring is report-only", err=True)
        raise typer.Exit(code=2)

    # Match numerator and denominator time bases; admission caps never enter here.
    actual_for_score = actual_total if basis == "expected-wall" else actual_work
    error_ratio = actual_for_score / estimated
    if not math.isfinite(error_ratio):
        typer.echo("Error: scoring ratio must be finite", err=True)
        raise typer.Exit(code=2)
    if 0.8 <= error_ratio <= 1.2:
        verdict = "ACCURATE"
    elif error_ratio < 0.8:
        verdict = "OVER-ESTIMATED"
    else:
        verdict = "UNDER-ESTIMATED"

    # Print comparison
    typer.echo("Estimation vs Actual Comparison")
    typer.echo("=" * 40)
    typer.echo(f"Basis:             {basis}")
    typer.echo(f"Source:            {raw.get('source') or 'caller-supplied observation'}")
    typer.echo(f"As of:             {raw.get('as_of') or 'unknown'}")
    typer.echo(f"Task type:         {raw.get('task_type', 'unknown')}")
    typer.echo(f"Estimated:         {estimated:.1f} min")
    typer.echo(f"Actual (work):     {actual_work:.1f} min")
    typer.echo(f"Actual (total):    {actual_total:.1f} min")
    typer.echo(f"Error ratio:       {error_ratio:.2f}")
    typer.echo(f"Verdict:           {verdict}")

    # Optionally store in calibration DB
    if db is not None:
        try:
            obs = _build_observation(raw, estimated, actual_work, actual_total, error_ratio, verdict)
        except (TypeError, ValueError) as exc:
            typer.echo(f"Error: Invalid observation field: {exc}", err=True)
            raise typer.Exit(code=2)

        try:
            with SQLiteCalibrationStore(db) as store:
                row_id = store.insert_observation(obs)
            typer.echo(f"\nObservation stored (id={row_id}) in {db}")
        except ValueError as exc:
            typer.echo(f"Error: Invalid observation field: {exc}", err=True)
            raise typer.Exit(code=2)
        except Exception as exc:
            typer.echo(f"Error storing observation: {exc}", err=True)
            raise typer.Exit(code=1)


def _build_observation(
    raw: dict[object, object],
    estimated: float,
    actual_work: float,
    actual_total: float,
    error_ratio: float,
    verdict: str,
) -> ObservationInput:
    modifiers_raw = raw.get("modifiers") or {}
    if not isinstance(modifiers_raw, dict):
        raise ValueError("'modifiers' must be a YAML mapping")  # noqa: TRY004 — content shape
    modifiers_should_have_been = raw.get("modifiers_should_have_been", {})
    if not isinstance(modifiers_should_have_been, dict):
        raise ValueError(  # noqa: TRY004 — content shape
            "'modifiers_should_have_been' must be a YAML mapping"
        )

    return ObservationInput(
        task_type=str(raw.get("task_type", "unknown")),
        estimated_secs=estimated * 60,
        actual_work_secs=actual_work * 60,
        actual_total_secs=actual_total * 60,
        error_ratio=error_ratio,
        file_count=int(raw.get("file_count", 0)),
        line_count=int(raw.get("line_count", 0)),
        test_count=int(raw.get("test_count", 0)),
        project_hash=str(raw.get("project_hash") or "unknown"),
        spec_clarity_modifier=float(modifiers_raw.get("spec_clarity", 1.0)),
        warm_context_modifier=float(modifiers_raw.get("warm_context", 1.0)),
        execution_mode=str(raw.get("execution_mode", "single")),
        review_mode=str(raw.get("review_mode", "none")),
        review_overhead_secs=float(raw.get("review_overhead_minutes", 0)) * 60,
        verdict=verdict,
        modifiers_should_have_been={
            str(key): float(value) for key, value in modifiers_should_have_been.items()
        },
    )
