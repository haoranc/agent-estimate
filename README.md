# agent-estimate

[![PyPI Version](https://img.shields.io/pypi/v/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![License](https://img.shields.io/pypi/l/agent-estimate)](https://github.com/haoranc/agent-estimate/blob/main/LICENSE)
[![CI](https://github.com/haoranc/agent-estimate/actions/workflows/ci.yml/badge.svg)](https://github.com/haoranc/agent-estimate/actions/workflows/ci.yml)

`agent-estimate` is a CLI for estimating delivery time of AI-agent work using:

- three-point PERT estimates
- METR-style model reliability thresholds
- dependency-aware wave planning
- explicit review overhead modes (`none`, `standard`, `complex`)
- non-coding task type estimation (brainstorm, research, config, docs)
- multi-agent session estimation

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

**Option 1 — From marketplace:**

```
/plugin marketplace add haoranc/agent-estimate
/plugin install agent-estimate@agent-estimate-marketplace
```

**Option 2 — Local development:**

```bash
claude --plugin-dir /path/to/agent-estimate
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

## GitHub Action

Run estimations directly in your CI/CD pipelines:

```yaml
- uses: haoranc/agent-estimate@v0
  with:
    issues: '11,12,14'
```

### Full Workflow Example

```yaml
name: Estimate
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  estimate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: haoranc/agent-estimate@v0
        with:
          issues: '11,12,14'
          output-mode: summary+pr-comment
```

### Action Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `issues` | yes | — | GitHub issue numbers (comma-separated) |
| `repo` | no | current repo | GitHub repo (owner/name) |
| `format` | no | `markdown` | Output format: `markdown` or `json` |
| `output-mode` | no | `summary` | `summary`, `pr-comment`, `step-output`, `summary+pr-comment` |
| `config` | no | — | Path to agent config YAML |
| `title` | no | `Agent Estimate Report` | Report title |
| `review-mode` | no | `standard` | Review tier: `none`, `standard`, `complex` |
| `spec-clarity` | no | `1.0` | Spec clarity modifier (0.3-1.3) |
| `warm-context` | no | `1.0` | Warm context modifier (0.3-1.15) |
| `agent-fit` | no | `1.0` | Agent fit modifier (0.9-1.2) |
| `task-type` | no | — | Task category: `coding`, `brainstorm`, `research`, `config`, `documentation` |
| `python-version` | no | `3.12` | Python version to use |
| `version` | no | latest | `agent-estimate` version to install |
| `token` | no | `${{ github.token }}` | GitHub token |

### Action Outputs

| Output | Description |
|--------|-------------|
| `report` | Full estimation report content |
| `expected-minutes` | Expected minutes (when `format: json`) |

## Codex Skill Layout

For Codex-oriented tooling, this repo includes a Codex-specific skill at:

- `.agent/skills/estimate/SKILL.md`

The Claude plugin skill remains at:

- `skills/estimate/SKILL.md`

Both skills cover the same CLI capabilities (`estimate`, `validate`, `calibrate`) but are phrased for their respective ecosystems.

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

| Model        | p80 threshold |
| ------------ | ------------- |
| Opus         | 90 minutes    |
| GPT-5.3      | 60 minutes    |
| GPT-5        | 50 minutes    |
| GPT-5.2      | 55 minutes    |
| Gemini 3 Pro | 45 minutes    |
| Sonnet       | 30 minutes    |

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

Apache License 2.0
