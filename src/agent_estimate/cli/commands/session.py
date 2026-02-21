"""Session command — multi-agent coordinated workflow estimation."""

from __future__ import annotations

from typing import NoReturn, Optional

import typer

from agent_estimate.core.session import (
    DEFAULT_COORDINATION_OVERHEAD_MINUTES,
    SESSION_TYPE_DURATIONS,
    estimate_session,
)


def run(
    agents: int = typer.Option(
        2,
        "--agents",
        "-a",
        help="Number of parallel agents in the session.",
        min=1,
    ),
    rounds: int = typer.Option(
        1,
        "--rounds",
        "-r",
        help="Number of sequential rounds.",
        min=1,
    ),
    type: str = typer.Option(  # noqa: A002
        "brainstorm",
        "--type",
        "-t",
        help=(
            "Session task type. Known types: "
            + ", ".join(sorted(SESSION_TYPE_DURATIONS))
            + "."
        ),
    ),
    coordination_overhead: Optional[float] = typer.Option(
        None,
        "--coordination-overhead",
        help=(
            f"Coordination overhead per round in minutes "
            f"(default: {DEFAULT_COORDINATION_OVERHEAD_MINUTES:.0f}m)."
        ),
    ),
    per_round_minutes: Optional[float] = typer.Option(
        None,
        "--per-round-minutes",
        help="Override per-agent per-round duration in minutes (skips type lookup).",
    ),
    format: str = typer.Option(  # noqa: A002
        "markdown",
        "--format",
        help="Output format: markdown or json.",
    ),
) -> None:
    """Estimate wall-clock and agent-minutes for a multi-agent session."""
    overhead = (
        coordination_overhead
        if coordination_overhead is not None
        else DEFAULT_COORDINATION_OVERHEAD_MINUTES
    )

    try:
        result = estimate_session(
            agents=agents,
            rounds=rounds,
            task_type=type,
            coordination_overhead_minutes=overhead,
            per_round_minutes=per_round_minutes,
        )
    except ValueError as exc:
        _error(str(exc), 2)

    if format == "json":
        import json

        data = {
            "agents": result.agents,
            "rounds": result.rounds,
            "task_type": result.task_type,
            "per_agent_round_minutes": result.per_agent_round_minutes,
            "coordination_overhead_minutes": result.coordination_overhead_minutes,
            "wall_clock_minutes": result.wall_clock_minutes,
            "agent_minutes": result.agent_minutes,
            "rounds_breakdown": list(result.rounds_breakdown),
        }
        typer.echo(json.dumps(data, indent=2), nl=False)
    elif format == "markdown":
        _render_markdown(result)
    else:
        _error(f"Unknown format: {format!r}. Use markdown or json.", 2)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_markdown(result: "SessionEstimate") -> None:  # type: ignore[name-defined]  # noqa: F821
    from agent_estimate.core.session import SessionEstimate  # noqa: PLC0415

    assert isinstance(result, SessionEstimate)

    wall_h, wall_m = divmod(int(result.wall_clock_minutes), 60)
    agent_h, agent_m = divmod(int(result.agent_minutes), 60)

    wall_str = f"{wall_h}h {wall_m}m" if wall_h else f"{wall_m}m"
    agent_str = f"{agent_h}h {agent_m}m" if agent_h else f"{agent_m}m"

    typer.echo("## Session Estimate\n")
    typer.echo("| Field                    | Value                      |")
    typer.echo("|--------------------------|----------------------------|")
    typer.echo(f"| Agents                   | {result.agents:<26} |")
    typer.echo(f"| Rounds                   | {result.rounds:<26} |")
    typer.echo(f"| Task type                | {result.task_type:<26} |")
    typer.echo(
        f"| Per-agent per-round      | {result.per_agent_round_minutes:.0f}m{'':<23} |"
    )
    typer.echo(
        f"| Coordination overhead    | {result.coordination_overhead_minutes:.0f}m / round{'':<15} |"
    )
    typer.echo(f"| **Wall-clock**           | **{wall_str}**{'':<{22 - len(wall_str)}} |")
    typer.echo(f"| **Agent-minutes**        | **{agent_str}**{'':<{22 - len(agent_str)}} |")

    if len(result.rounds_breakdown) > 1:
        typer.echo("\n### Round breakdown\n")
        for i, rd in enumerate(result.rounds_breakdown, 1):
            h, m = divmod(int(rd + result.coordination_overhead_minutes), 60)
            rstr = f"{h}h {m}m" if h else f"{m}m"
            typer.echo(f"- Round {i}: {rstr} wall-clock")


def _error(message: str, exit_code: int) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=exit_code)
