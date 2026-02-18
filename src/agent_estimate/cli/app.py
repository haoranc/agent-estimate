"""Typer application entrypoint."""

import typer

from agent_estimate.cli.commands.calibrate import run as run_calibrate
from agent_estimate.cli.commands.estimate import run as run_estimate
from agent_estimate.cli.commands.validate import run as run_validate

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Estimate AI-agent delivery time using PERT, METR thresholds, and wave planning.",
)

app.command("estimate")(run_estimate)
app.command("calibrate")(run_calibrate)
app.command("validate")(run_validate)


def main() -> None:
    """Run the CLI app."""
    app()


if __name__ == "__main__":
    main()
