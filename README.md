# agent-estimate

[![PyPI Version](https://img.shields.io/pypi/v/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![Python Versions](https://img.shields.io/pypi/pyversions/agent-estimate)](https://pypi.org/project/agent-estimate/)
[![License](https://img.shields.io/pypi/l/agent-estimate)](https://github.com/kiloloop/agent-estimate/blob/main/LICENSE)
[![CI](https://github.com/kiloloop/agent-estimate/actions/workflows/ci.yml/badge.svg)](https://github.com/kiloloop/agent-estimate/actions/workflows/ci.yml)

**Know before you build.**

PERT estimates for AI-agent tasks — how long, which model's reliable enough, and the human-equivalent cost. In one command.

**[Website](https://kiloloop.com/agent-estimate/)** · [Compare](https://kiloloop.com/agent-estimate/compare/) · [PyPI](https://pypi.org/project/agent-estimate/)

## Why

AI agents can write the code — but *how long will the task actually take?* Manual estimation is slow and biased toward optimism; no estimate means scope creep and missed deadlines. The gap between "agents can do it" and "we know when it'll be done" is where projects break down.

`agent-estimate` closes that gap in one command: a three-point PERT timeline calibrated on real agent runs, plus a human-speed comparison so you see the compression before you spend the compute. It sizes the task, picks a tier, routes it to a model, and flags when the work runs past that model's reliability horizon — calibrated forecasts in seconds, not meetings.

Multi-model matters because the models aren't interchangeable. Opus 4.7, GPT-5.5, and Gemini 3.1 have different reliability horizons ([METR p80](https://metr.org/)) and different costs per turn. A safe 40-minute job for one model is a coin flip for another. agent-estimate models the whole fleet, not a single agent — so the number reflects who actually runs the work.

## Quick Start

> First estimate: 30 seconds to install. Every one after: instant.

### With your agent (recommended)

Paste this into your Claude Code or Codex session:

~~~
Install the agent-estimate plugin (https://github.com/kiloloop/agent-estimate) and
estimate this task for me: "Implement OAuth 2.0 flow (Google + GitHub)". Tell me the
expected time, the human-speed equivalent, and the compression ratio.
~~~

Your agent installs the tool, runs the estimate, and reads back the numbers. Nothing to memorize — describe the task in plain English and let the agent translate to flags.

For a whole backlog:

~~~
Estimate every open issue in this repo with agent-estimate, group them into parallel
waves, and tell me the total wall-clock time for a 3-agent fleet versus doing them
sequentially myself.
~~~

### Manual

```bash
pip install agent-estimate
agent-estimate estimate "your task description here"
```

No config required — sensible defaults for a 3-agent fleet (Claude, Codex, Gemini). Point it at a file or GitHub issues when you're ready:

```bash
agent-estimate estimate --file tasks.txt
agent-estimate estimate --repo myorg/myrepo --issues 11,12,14
agent-estimate session --agents 3 --rounds 2 --type review
```

## How It Works

agent-estimate produces three-point [PERT](https://en.wikipedia.org/wiki/Program_evaluation_and_review_technique) estimates calibrated for agents, not humans:

- **Tier classification** — auto-sizes tasks XS→XL from complexity signals
- **PERT math** — optimistic / most-likely / pessimistic, weighted to an expected value
- **Human comparison** — a per-task-type multiplier, so you see the compression
- **METR thresholds** — warns when an estimate exceeds a model's p80 reliability horizon
- **Wave planning** — schedules independent tasks in parallel across the fleet
- **Review overhead** — models review cycles as additive cost (`standard`, `complex`, `3-round`)
- **Modifiers** — `--spec-clarity`, `--warm-context`, `--agent-fit` tune the estimate

### Task types

| Type | Flag | Models |
|------|------|--------|
| Coding | (default) | Feature work, fixes, refactors |
| Research | `--type research` | Audits, investigations, analysis |
| Documentation | `--type documentation` | API docs, guides, changelogs |
| Brainstorm | `--type brainstorm` | Ideation, spikes, design exploration |
| Config/SRE | `--type config` | Deploys, infra, CI/CD |
| Frontend/UI | `--type frontend` | Content patches vs. component builds |
| App dev | `--type app_dev` | App shells, desktop/mobile builds |

### METR thresholds (defaults)

| Model | p80 threshold |
|-------|---------------|
| Opus 4.7 | 90 min |
| GPT-5.5 | 90 min |
| GPT-5.4 | 60 min |
| Gemini 3.1 Pro | 45 min |
| Sonnet 4.6 | 30 min |
| Haiku 4.5 | 15 min |

`opus_4_x` is a forward-compatible alias that resolves to the current Opus threshold. Legacy keys (`opus_4_6`, GPT-5/5.2/5.3, Gemini 3 Pro, Sonnet) stay supported. Estimates are calibrated against Claude Code (Opus 4.7, high thinking) and Codex (GPT-5.4/5.5, extra-high) — shift with `--spec-clarity` and `--warm-context` for other setups.

## Examples

Real estimates from production use — including the misses.

**The tool, estimating its own docs.** We sized this v0.7.0 skill-and-README refresh at ~30 minutes. It took 28.

**An honest over-estimate.** We pre-registered a UI mockup build at ~95 minutes with no prior app-dev data. Two agents did it in parallel in 12 and 25 minutes — a 4–8x over-estimate. agent-estimate now ships an `app_dev` prior shaped by that result. The miss stays in the README because calibration means showing where you were wrong.

**Three tasks, three agents, in parallel** — what the tool prints, including the METR reliability flags. Input is the three-task `tasks.txt` from [`examples/multi-agent.md`](./examples/multi-agent.md); the output below is captured from a real run, trimmed to the timeline and warnings (the full report — per-task PERT table, wave plan, agent loads — is in that example):

```text
$ agent-estimate estimate --file tasks.txt

## Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 44.7m |
| Expected case | 75.4m |
| Worst case | 117.2m |
| Human-speed equivalent | 608.2m |
| Compression ratio | 8.07x |
| Review overhead (per-task, pre-amortization) | 45m |

## METR Warnings

- **Add known_debt.md as standard protocol memory file**: Estimate (75m) exceeds gpt_5_4 p80 threshold (60m). Consider splitting the task.
- **Write quickstart guide with protocol comparison table**: Estimate (75m) exceeds gemini_3_1_pro p80 threshold (45m). Consider splitting the task.
```

~75 minutes wall-clock versus ~10.1 hours of sequential human work, at an estimated $3.51 fleet cost — plus two flags that the Codex- and Gemini-assigned tasks run past their models' p80 reliability horizons, so you split them or add a checkpoint before dispatching. The same three tasks were later run by real agents; the retro is in the example file. More in [`examples/`](./examples/) — coding S/M, research, documentation, multi-agent.

## Integrations

### Claude Code plugin

```
/plugin marketplace add kiloloop/agent-estimate
/plugin install agent-estimate@agent-estimate-marketplace
```

```
/estimate Add a login page with OAuth
/estimate --file spec.md
/estimate --issues 1,2,3 --repo myorg/myrepo
/estimate validate observation.yaml
/estimate calibrate
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
  issues: read
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
| `review-mode` | no | `standard` | Review tier: `none`, `standard`, `complex`, `3-round` |
| `spec-clarity` | no | `1.0` | Spec clarity modifier (0.3–1.3) |
| `warm-context` | no | `1.0` | Warm context modifier (0.3–1.15) |
| `agent-fit` | no | `1.0` | Agent fit modifier (0.9–1.2) |
| `task-type` | no | — | Category: `coding`, `brainstorm`, `research`, `config`, `documentation`, `frontend`, `app_dev` |
| `python-version` | no | `3.12` | Python version to use |
| `version` | no | latest | `agent-estimate` version to install |
| `token` | no | `${{ github.token }}` | GitHub token |

| Output | Description |
|--------|-------------|
| `report` | Full estimation report content |
| `expected-minutes` | Expected minutes (when `format: json`) |

</details>

### Skill layout

Skills follow the [oacp-skills](https://github.com/kiloloop/oacp-skills) convention:

```
skills/estimate/
  skill.yaml            # machine-readable metadata
  README.md             # human-readable docs
  shared/INTENT.md      # shared intent across runtimes
  claude/SKILL.md       # Claude Code skill definition
  codex/SKILL.md        # Codex skill definition
```

Both runtime slices cover the same CLI (`estimate`, `validate`, `calibrate`), phrased for their respective ecosystems.

## Configuration

### Agent fleet

Pass a config to model your own fleet:

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

### Output formats

```bash
agent-estimate estimate "Refactor auth pipeline" --format json   # machine-readable
agent-estimate estimate --repo myorg/myrepo --issues 11,12,14    # from GitHub issues
agent-estimate estimate --file tasks.txt                          # from file
agent-estimate estimate "Follow-up fix" --history-file data.json  # auto warm-context
```

When `--warm-context` is omitted, the CLI can auto-infer it from `--history-file`;
if no history file is passed and `./data.json` exists, that file is used as the
default dispatch history source.

### Session estimates

Use `agent-estimate session` for coordinated workflows where multiple agents run
rounds of brainstorm, review, research, documentation, config, or coding work:

```bash
agent-estimate session --agents 3 --rounds 2 --type review
agent-estimate session --agents 4 --rounds 1 --per-round-minutes 25 --format json
```

The command reports wall-clock time, total agent-minutes, coordination overhead,
and per-round breakdowns.

### Calibration

Validate estimates against observed outcomes and build a calibration database:

```bash
agent-estimate validate observation.yaml --db ~/.agent-estimate/calibration.db
```

## Project

- **[Website](https://kiloloop.com/agent-estimate/)** — landing page, live demo, and the [estimate comparison view](https://kiloloop.com/agent-estimate/compare/).
- **[OACP](https://github.com/kiloloop/oacp)** — coordinate the agents you just estimated. Open Agent Coordination Protocol for multi-agent async workflows.
- **[oacp-skills](https://github.com/kiloloop/oacp-skills)** — the skill bundle agent-estimate's `/estimate` ships in.
- **[kiloloop](https://github.com/kiloloop)** — the rest of the ecosystem.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full workflow.

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
