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

`agent-estimate` closes that gap in one command: a three-point PERT timeline built from priors drawn from 33 internal coding dispatches and 6 brainstorm dispatches, plus a human-speed comparison so you see the compression before you spend the compute. It sizes the task, picks a tier, routes it to a model, and flags when the work exceeds that model's configured reliability policy — forecasts in seconds, not meetings.

Multi-model matters because the models aren't interchangeable. A measured p80 horizon is the human-expert task duration at which a model is estimated to succeed 80% of the time. The shipped limits below are instead provenance-labeled local policy (unmeasured), because current models such as Opus 4.7 and GPT-5.5 do not have matching published measurements. agent-estimate models the whole fleet, not a single agent — so the number reflects who actually runs the work.

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

agent-estimate produces three-point [PERT](https://en.wikipedia.org/wiki/Program_evaluation_and_review_technique) estimates from agent-work priors, not human-duration estimates:

- **Tier classification** — auto-sizes tasks XS→XL from complexity signals
- **PERT math** — optimistic / most-likely / pessimistic, weighted to an expected value
- **Human comparison** — a per-task-type multiplier, so you see the compression
- **Reliability policies** — warns when friction-adjusted work exceeds a provenance-labeled model limit
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

### Reliability policy defaults

| Model | Work limit | Basis |
|-------|------------|-------|
| Opus 4.7 | 90 min | Local policy (unmeasured) |
| GPT-5.5 | 90 min | Local policy (unmeasured) |
| GPT-5.4 | 60 min | Local policy (unmeasured) |
| Gemini 3.1 Pro | 45 min | Local policy (unmeasured) |
| Sonnet 4.6 | 30 min | Local policy (unmeasured) |
| Haiku 4.5 | 15 min | Local policy (unmeasured) |

Every row records `basis`, `source`, `source_version`, and `as_of` in `metr_thresholds.yaml`; the defaults above come from the agent-estimate v0.7.5 local-policy registry as of 2026-08-23. `opus_4_x` is a forward-compatible alias that resolves to the current Opus policy. Legacy keys (`opus_4_6`, GPT-5/5.2/5.3, Gemini 3 Pro, Sonnet) stay supported. The bundled thinking-level baseline is Claude Code high and Codex extra-high — shift with `--spec-clarity` and `--warm-context` for other setups.

## Examples

Real estimates from production use — including the misses.

**The tool, estimating its own docs.** We sized this v0.7.0 skill-and-README refresh at ~30 minutes. It took 28.

**An honest over-estimate.** We pre-registered a UI mockup build at ~95 minutes with no prior app-dev data. Two agents did it in parallel in 12 and 25 minutes — a 4–8x over-estimate. agent-estimate now ships an `app_dev` prior shaped by that result. The miss stays in the README because calibration means showing where you were wrong.

**Three tasks, three agents, in parallel** — what the tool prints, including the reliability-policy flags. Input is the three-task `tasks.txt` from [`examples/multi-agent.md`](./examples/multi-agent.md); the output below is captured from a real run, trimmed to the timeline and warnings (the full report — per-task PERT table, wave plan, assumptions, and agent loads — is in that example):

```text
$ agent-estimate estimate --file tasks.txt

## Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 44.7m |
| Expected case | 75.4m |
| Worst case | 117.2m |
| Human-speed equivalent | 473.1m |
| Compression ratio | 6.28x |
| Review overhead (per-task, pre-amortization) | 45m |

## Reliability Horizon Warnings

- **Add known_debt.md as standard protocol memory file**: Work estimate (60.4m) exceeds gpt_5_4 local reliability policy (unmeasured) (60m). Consider splitting the task.
- **Write quickstart guide with protocol comparison table**: Work estimate (60.4m) exceeds gemini_3_1_pro local reliability policy (unmeasured) (45m). Consider splitting the task.
```

~75 minutes wall-clock versus the work-only human equivalent, at an estimated $3.51 fleet cost — plus policy flags when assigned work exceeds a model's configured limit, so you split it or add a checkpoint before dispatching. Human review is modeled separately. The same three tasks were later run by real agents; the retro is in the example file. More in [`examples/`](./examples/) — coding S/M, research, documentation, multi-agent.

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

Available on the [GitHub Marketplace](https://github.com/marketplace/actions/agent-estimate):

```yaml
- uses: kiloloop/agent-estimate@v0
  with:
    issues: '11,12,14'
```

The report goes wherever `output-mode` points: the job summary (`summary`, the default), a PR comment (`pr-comment`), an issue comment (`issue-comment`), or a step output for downstream steps (`step-output`) — combinable with `+` (e.g. `summary+pr-comment`).

Grant only the permissions required by the selected output modes:

| Output mode | Required `permissions:` |
|-------------|--------------------------|
| `summary` | `issues: read` when issue input comes from a private repository |
| `pr-comment` | `issues: read` when issue input comes from a private repository, plus `pull-requests: write` |
| `issue-comment` | `issues: write` |
| `step-output` | `issues: read` when issue input comes from a private repository |

Add `contents: read` only when the calling workflow uses `actions/checkout`; the Action itself does not require a checkout. Combined modes need the union of their rows.

By default, the Action installs `agent-estimate` from its own checked-out
`GITHUB_ACTION_PATH`, so the Python implementation stays coupled to the
`uses:` ref. Set `version` only when you deliberately want a published package
version instead. Each run exposes the resolved `package-version` and
`install-source`; Markdown reports repeat both values in their footer.

On offline self-hosted runners, allow the source install's isolated build
environment to resolve `hatchling>=1.32,<2` and the package dependencies from a
configured package index or cache. Merely checking out the Action does not
pre-provision the build backend used by pip's PEP 517 isolation.

<details>
<summary>Estimate on every PR</summary>

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
      - uses: actions/checkout@v7
      - uses: kiloloop/agent-estimate@v0
        with:
          issues: '11,12,14'
          output-mode: summary+pr-comment
```

</details>

<details>
<summary>Auto-estimate on label</summary>

Label an issue `estimate` and the Action posts or updates one marked estimate comment (the label match is exact and case-sensitive):

```yaml
name: Auto-estimate
on:
  issues:
    types: [labeled]

permissions:
  contents: read
  issues: write

jobs:
  estimate:
    if: github.event.label.name == 'estimate'
    runs-on: ubuntu-latest
    steps:
      - uses: kiloloop/agent-estimate@v0
        with:
          issues: ${{ github.event.issue.number }}
          output-mode: issue-comment
          title: 'Agent Estimate — issue #${{ github.event.issue.number }}'
```

This repo runs it on itself — see [`.github/workflows/auto-estimate.yml`](.github/workflows/auto-estimate.yml).

</details>

<details>
<summary>Gate on the estimate (JSON step output)</summary>

With `format: json` the Action exposes `expected-minutes` as a step output — use it to gate or route downstream steps:

```yaml
name: Estimate gate
on:
  issues:
    types: [labeled]

permissions:
  issues: read

jobs:
  gate:
    if: github.event.label.name == 'estimate'
    runs-on: ubuntu-latest
    steps:
      - uses: kiloloop/agent-estimate@v0
        id: estimate
        with:
          issues: ${{ github.event.issue.number }}
          format: json
          output-mode: step-output
      - name: Flag oversized tasks
        if: steps.estimate.outputs.expected-minutes != '' && fromJSON(steps.estimate.outputs.expected-minutes) > 120
        env:
          AE_MINUTES: ${{ steps.estimate.outputs.expected-minutes }}
        run: echo "::warning::Expected ${AE_MINUTES} min — consider splitting before dispatching an agent."
```

The full JSON report is available as `steps.estimate.outputs.report` for custom processing.
Its footer records `engine_version` and `registry_version`. Agent-load rows expose
the five-minute-turn estimate as `heuristic_cost`; `estimated_cost` remains as a
compatibility alias until the v0.8 report schema.

</details>

<details>
<summary>Action inputs and outputs</summary>

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `issues` | yes | — | GitHub issue numbers (comma-separated) |
| `repo` | no | current repo | GitHub repo (owner/name) |
| `format` | no | `markdown` | Output format: `markdown` or `json` |
| `output-mode` | no | `summary` | `summary`, `pr-comment`, `issue-comment`, `step-output`, or a `+`-joined combo |
| `config` | no | — | Path to agent config YAML |
| `title` | no | `Agent Estimate Report` | Report title |
| `review-mode` | no | `standard` | Review tier: `none`, `standard`, `complex`, `3-round` |
| `spec-clarity` | no | `1.0` | Spec clarity modifier (0.3–1.3) |
| `warm-context` | no | `1.0` | Warm context modifier (0.3–1.15) |
| `agent-fit` | no | `1.0` | Agent fit modifier (0.9–1.2) |
| `task-type` | no | — | Category: `coding`, `brainstorm`, `research`, `config`, `documentation`, `frontend`, `app_dev` |
| `python-version` | no | `3.12` | Python version to use |
| `version` | no | Action ref | Published `agent-estimate` version override |
| `token` | no | `${{ github.token }}` | GitHub token |

| Output | Description |
|--------|-------------|
| `report` | Full estimation report content |
| `expected-minutes` | Expected minutes (when `format: json`) |
| `package-version` | Resolved `agent-estimate` package version used by the run |
| `install-source` | `action-path` by default, or `version-override` when `version` is set |

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
  metr_fallback_threshold: 45.0
```

Legacy configs that set `settings.review_overhead` emit a deprecation warning;
the field is optional and ignored, and it will be removed in v0.8. Remove it and
select additive review overhead with `--review-mode` instead.

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
