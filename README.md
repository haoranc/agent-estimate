# agent-estimate

[![PyPI Version](https://img.shields.io/pypi/v/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![License](https://img.shields.io/pypi/l/agent-estimate)](https://github.com/haoranc/agent-estimate/blob/main/LICENSE)
[![CI](https://github.com/haoranc/agent-estimate/actions/workflows/ci.yml/badge.svg)](https://github.com/haoranc/agent-estimate/actions/workflows/ci.yml)

`agent-estimate` is a CLI for estimating delivery time of AI-agent work using:

- three-point PERT estimates
- METR-style model reliability thresholds
- dependency-aware wave planning
- explicit review overhead modes (`none`, `self`, `2x-lgtm`)

## Installation

Install from PyPI:

```bash
pip install agent-estimate
```

Install from source for development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Quick Start

Estimate one task from the command line:

```bash
agent-estimate estimate "Implement OAuth login flow"
```

Show version:

```bash
agent-estimate --version
```

## Claude Code Plugin

`agent-estimate` includes a Claude Code plugin for interactive estimation in Claude Code sessions.

### Install

```bash
/install-plugin haoranc/agent-estimate
```

**Prerequisite**: The CLI must be installed first: `pip install agent-estimate`

### Plugin Usage

```
/estimate Add a login page with OAuth
/estimate --file spec.md
/estimate --issues 1,2,3 --repo myorg/myrepo
/validate-estimate observation.yaml
/calibrate
```

## Codex Skill Layout

For Codex-oriented tooling, this repo also includes a `.agent` skill mirror:

- `.agent/skills/estimate/SKILL.md`

It is kept in sync with the canonical skill definition at:

- `skills/estimate/SKILL.md`

## Usage Examples

Estimate tasks from a text file:

```bash
agent-estimate estimate --file tests/fixtures/tasks_multi.txt
```

Output JSON for downstream tooling:

```bash
agent-estimate estimate "Refactor auth pipeline" --format json
```

Estimate directly from GitHub issues:

```bash
agent-estimate estimate --repo haoranc/agent-estimate --issues 11,12,14
```

Validate estimate vs observed outcome and persist to calibration DB:

```bash
agent-estimate validate tests/fixtures/observation_valid.yaml --db ~/.agent-estimate/calibration.db
```

## TestPyPI Validation

Manual local publish (requires TestPyPI API token configured for `twine`):

```bash
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple agent-estimate
```

Or run the GitHub Actions workflow `TestPyPI Dry Run` to publish and smoke-test install end-to-end.

## Default METR Thresholds

The default model thresholds are defined in `src/agent_estimate/metr_thresholds.yaml`:

| Model | p80 threshold |
| --- | --- |
| Opus | 90 minutes |
| GPT-5.3 | 60 minutes |
| GPT-5 | 50 minutes |
| GPT-5.2 | 55 minutes |
| Gemini 3 Pro | 45 minutes |
| Sonnet | 30 minutes |

## Agent Config Example

Pass a custom config file with `--config`:

```yaml
agents:
  - name: Claude
    capabilities: [planning, implementation, review]
    parallelism: 2
    cost_per_turn: 0.12
    model_tier: frontier
  - name: Codex
    capabilities: [implementation, debugging, testing]
    parallelism: 3
    cost_per_turn: 0.08
    model_tier: production
settings:
  friction_multiplier: 1.15
  inter_wave_overhead: 0.25
  review_overhead: 0.2
  metr_fallback_threshold: 45.0
```

Then run:

```bash
agent-estimate estimate "Ship packaging flow" --config ./my_agents.yaml
```

## Contributing

1. Fork and create a branch from `main`.
2. Install dev dependencies:
   ```bash
   pip install -e '.[dev]'
   ```
3. Run checks:
   ```bash
   ruff check .
   pytest -q
   ```
4. Open a pull request with a clear summary and test evidence.

## License

MIT
