# agent-estimate

Open-source effort estimation for AI coding agents.

`agent-estimate` estimates wall-clock delivery time for agent-driven work using three-point PERT estimates, model reliability thresholds, and dependency-aware wave planning.

## Status

- Version: `0.0.1`
- Stage: Planning / scaffolded CLI
- Scope in progress: estimation engine, calibration store, and GitHub ingestion

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## CLI Usage (Scaffold)

```bash
agent-estimate --help
agent-estimate estimate "Implement OAuth login flow"
agent-estimate calibrate
agent-estimate validate docs/spec.md
```

Current commands are stubs and provide placeholder output while core modules are implemented.

## Project Layout

- `src/agent_estimate/cli/` — Typer app and command entrypoints
- `src/agent_estimate/core/` — estimation, sizing, decomposition, and wave logic
- `src/agent_estimate/adapters/` — config, SQLite, and GitHub integration adapters
- `src/agent_estimate/render/` — markdown/json output renderers
- `src/agent_estimate/skill/` — wrappers for agent skill integration
- `metr_thresholds.yaml` — baseline p80 model thresholds

## METR Threshold Baseline

- Opus: 90 minutes
- GPT-5.3: 60 minutes
- Gemini 3 Pro: 45 minutes
- Sonnet: 30 minutes

## Development Checks

```bash
ruff check .
pytest
```

## License

MIT
