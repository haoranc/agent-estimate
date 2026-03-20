# agent-estimate

[![PyPI Version](https://img.shields.io/pypi/v/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![License](https://img.shields.io/pypi/l/agent-estimate)](https://github.com/kiloloop/agent-estimate/blob/main/LICENSE)
[![CI](https://github.com/kiloloop/agent-estimate/actions/workflows/ci.yml/badge.svg)](https://github.com/kiloloop/agent-estimate/actions/workflows/ci.yml)

**Know what an AI task will cost before you run it.**

`agent-estimate` tells you how long an AI agent will take — and how that compares to doing it yourself.

```
$ agent-estimate estimate "Implement OAuth 2.0 flow (Google + GitHub)"
```

| Metric | Value |
| --- | --- |
| Expected case | 75.4m |
| Human-speed equivalent | 190.9m |
| **Compression ratio** | **2.53x** |

One command. Three numbers. Now you know whether to dispatch an agent or do it yourself.

## See it in action

### Single task — coding

```bash
$ agent-estimate estimate "Implement OAuth 2.0 flow (Google + GitHub)"
```

| Metric | Value |
| --- | --- |
| Task | Implement OAuth 2.0 flow (Google + GitHub) |
| Tier / Agent | M / Claude |
| Base PERT (O/M/P) | 25m / 50m / 90m (E=52.5m) |
| Best case | 44.7m |
| Expected case | 75.4m |
| Worst case | 117.2m |
| Human-speed equivalent | 190.9m |
| **Compression ratio** | **2.53x** |
| Review overhead | +15m (standard) |
| Estimated cost | $1.45 |

A medium coding task. Your agent finishes in ~75 minutes. Doing it yourself? ~3 hours. ([Full output](./examples/coding-m.md))

### Single task — research

```bash
$ agent-estimate estimate "Audit dependencies for known CVEs" --type research
```

| Metric | Value |
| --- | --- |
| Task | Audit dependencies for known CVEs |
| Tier / Agent | S / Claude |
| Base PERT (O/M/P) | 10m / 20m / 30m (E=20m) |
| Expected case | 38m |
| Human-speed equivalent | 99m |
| **Compression ratio** | **2.61x** |
| Estimated cost | $0.55 |

Research tasks have high human-multipliers — pattern matching across hundreds of dependencies is exactly where agents shine. ([Full output](./examples/research.md))

### Multi-agent session — 3 tasks in parallel

```bash
$ agent-estimate estimate --file tasks.txt
```

Where `tasks.txt` contains:
```
Implement OAuth 2.0 flow (Google + GitHub)
Write unit tests for OAuth flow
Write API reference for auth module
```

| Task | Tier | Agent | Expected | Human Equiv |
| --- | --- | --- | --- | --- |
| Implement OAuth 2.0 flow | M | Codex | 52.5m | 190.9m |
| Write unit tests for OAuth flow | M | Gemini | 52.5m | 190.9m |
| Write API reference for auth module | L | Claude | 100.8m | 327.6m |

| Metric | Value |
| --- | --- |
| Wave 0 | All 3 tasks in parallel (Claude + Codex + Gemini) |
| Expected case | 131m |
| Human-speed equivalent | 709.5m |
| **Compression ratio** | **5.42x** |
| Estimated cost | $4.84 |

Three agents working in parallel. ~2 hours wall clock vs ~12 hours sequential human work. That's the power of fleet estimation — you see the compression before you commit the compute. ([Full output](./examples/multi-agent.md))

> More examples in [`examples/`](./examples/) — coding S/M, research, documentation, and multi-agent sessions.

## Try it now

```bash
pip install agent-estimate
```

```bash
agent-estimate estimate "your task description here"
```

That's it. No config needed — sensible defaults for a 3-agent fleet (Claude, Codex, Gemini).

## What it does

`agent-estimate` produces three-point [PERT](https://en.wikipedia.org/wiki/Program_evaluation_and_review_technique) estimates calibrated for AI agents, not humans:

- **Tier classification** — auto-sizes tasks as XS/S/M/L/XL based on complexity signals
- **PERT math** — optimistic, most-likely, pessimistic with weighted expected value
- **Human comparison** — multiplier per task type (coding, research, docs) so you see the compression
- **METR thresholds** — warns when estimates exceed model reliability limits ([METR p80 benchmarks](https://metr.org/))
- **Wave planning** — dependency-aware scheduling across multiple agents with parallelism
- **Review overhead** — models review cycles as flat additive cost, amortized per agent per wave
- **Modifiers** — tune estimates with `--spec-clarity`, `--warm-context`, `--agent-fit`

### Supported task types

| Type | Flag | What it models |
|------|------|---------------|
| Coding | (default) | Feature work, bug fixes, refactors — tier-based PERT |
| Research | `--type research` | Audits, investigations, analysis — flat PERT with depth scaling |
| Documentation | `--type documentation` | API docs, guides, changelogs |
| Brainstorm | `--type brainstorm` | Ideation, spikes, design exploration |
| Config/SRE | `--type config` | Deploys, infra changes, CI/CD work |

## Integrations

### Claude Code Plugin

```
/plugin marketplace add kiloloop/agent-estimate
/plugin install agent-estimate@agent-estimate-marketplace
```

Then use directly in Claude Code sessions:

```
/estimate Add a login page with OAuth
/estimate --file spec.md
/estimate --issues 1,2,3 --repo myorg/myrepo
/validate-estimate observation.yaml
/calibrate
```

### GitHub Action

```yaml
- uses: kiloloop/agent-estimate@v0
  with:
    issues: '11,12,14'
```

<details>
<summary>Full workflow example</summary>

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
      - uses: kiloloop/agent-estimate@v0
        with:
          issues: '11,12,14'
          output-mode: summary+pr-comment
```

</details>

<details>
<summary>Action inputs and outputs</summary>

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

| Output | Description |
|--------|-------------|
| `report` | Full estimation report content |
| `expected-minutes` | Expected minutes (when `format: json`) |

</details>

### Codex Skill

Codex-specific skill at `.agent/skills/estimate/SKILL.md`. Claude plugin skill at `skills/estimate/SKILL.md`.

## Configuration

### Agent fleet

Pass a custom config to model your own agent fleet:

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

```bash
agent-estimate estimate "Ship packaging flow" --config ./my_agents.yaml
```

### Default METR thresholds

| Model          | p80 threshold |
| -------------- | ------------- |
| Opus 4.6       | 90 minutes    |
| GPT-5.4        | 60 minutes    |
| Gemini 3.1 Pro | 45 minutes    |
| Sonnet 4.6     | 30 minutes    |
| Haiku 4.5      | 15 minutes    |

Legacy model keys (Opus, GPT-5/5.2/5.3, Gemini 3 Pro, Sonnet) are still supported for backward compatibility.

> **Note:** Estimates are calibrated against Claude Code (Opus 4.6, High thinking) and Codex (GPT-5.4, Extra High thinking). Different thinking levels or model versions may shift estimates — adjust with `--spec-clarity` and `--warm-context` modifiers as needed.

### Output formats

```bash
agent-estimate estimate "Refactor auth pipeline" --format json    # machine-readable
agent-estimate estimate --repo myorg/myrepo --issues 11,12,14     # from GitHub issues
agent-estimate estimate --file tasks.txt                           # from file
```

### Calibration

Validate estimates against observed outcomes and build a calibration database:

```bash
agent-estimate validate observation.yaml --db ~/.agent-estimate/calibration.db
```

## Related

**[OACP](https://github.com/kiloloop/oacp)** — Coordinate the agents you just estimated. Open Agent Coordination Protocol for multi-agent async workflows.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full workflow and expectations.

```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

## Community

- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [Security Policy](./SECURITY.md)
- [Support](./SUPPORT.md)
- [Changelog](./CHANGELOG.md)

## License

Apache License 2.0
