---
name: estimate
description: Estimate effort for AI coding agent tasks using PERT three-point estimation with METR reliability thresholds and wave planning.
disable-model-invocation: true
---

# /estimate — AI Agent Effort Estimation

Run PERT three-point estimation with METR reliability thresholds and wave planning for one or more tasks.

## Usage

```
/estimate <task description>
/estimate --file <path>
/estimate --issues <numbers> --repo <owner/name>
/estimate --config <path> <task>
/estimate --format json <task>
/estimate --review-mode none <task>
/estimate --title "My Report" <task>
/validate-estimate <observation.yaml>
/calibrate
```

## Instructions

When the user invokes this skill, follow these steps:

### 1. Parse the invocation

Determine which subcommand to run based on context:

| Invocation pattern            | Subcommand                 |
| ----------------------------- | -------------------------- |
| `/estimate ...` with any args | `agent-estimate estimate`  |
| `/validate-estimate <file>`   | `agent-estimate validate`  |
| `/calibrate`                  | `agent-estimate calibrate` |

### 2. Build the CLI command

#### Global flags (all subcommands)

| Flag        | Short | Description                                                 |
| ----------- | ----- | ----------------------------------------------------------- |
| `--verbose` | `-v`  | Enable debug logging — useful when a command exits non-zero |

#### For `/estimate`

Parse these optional flags from user input and pass them through verbatim:

| Flag                   | Short | Description                                          |
| ---------------------- | ----- | ---------------------------------------------------- |
| `--file <path>`        | `-f`  | Path to task file (one task per line)                |
| `--config <path>`      | `-c`  | Path to config YAML with agent definitions           |
| `--format <fmt>`       |       | Output format: `markdown` (default) or `json`        |
| `--type <category>`    |       | Task category: `coding`, `brainstorm`, `research`, `config`, `documentation`, `frontend`, `app_dev`. Omit to auto-detect. |
| `--review-mode <mode>` |       | Review overhead tier: `none` (0 m), `standard` (15 m, default), `complex` (25 m), `3-round` (35 m) |
| `--spec-clarity <n>`   |       | Spec-clarity modifier (`0.3`–`1.3`)                  |
| `--warm-context <n>`   |       | Warm-context modifier (`0.3`–`1.15`)                 |
| `--agent-fit <n>`      |       | Agent-fit modifier (`0.9`–`1.2`)                     |
| `--issues <nums>`      | `-i`  | Comma-separated GitHub issue numbers                 |
| `--repo <owner/name>`  | `-r`  | GitHub repo (required with `--issues`)               |
| `--title <text>`       | `-t`  | Report title                                         |

If none of `--file`, `--issues`, or a task description is provided, prompt the user:
> Please provide a task description, `--file <path>`, or `--issues <nums> --repo <owner/name>`.

**Task categories** (`--type`, or auto-detected when omitted):

- `coding` — feature work, bug fixes, tests, refactors (default tiered PERT model).
- `brainstorm` — pure ideation and design exploration.
- `research` — audits, investigations, OSS comparisons, citation/source-grounded work. Research-grounded brainstorms (citation, OSS, benchmark, source, or landscape signals) route here instead of the flat brainstorm band.
- `config` — deploys, infra, CI/CD, runbooks, monitoring, SRE.
- `documentation` — API docs, guides, README changes, changelogs.
- `frontend` — UI/page work (content patches use 15/25/40; page builds use 40/60/90).
- `app_dev` — app shells and desktop/mobile builds (cold generic L-style prior; use modifiers for warm or highly specified work).

#### For `/validate-estimate`

The argument after `/validate-estimate` is the observation YAML file path. Optionally pass `--db <path>` if provided.

#### For `/calibrate`

Optionally pass `--db <path>` if provided. Default: `~/.agent-estimate/calibration.db`.

### 3. Run the command

Execute the CLI via Bash:

```bash
agent-estimate estimate "Add login button"
agent-estimate estimate --file tasks.md
agent-estimate estimate --issues 1,2,3 --repo org/name
agent-estimate estimate --config custom.yaml "Add login button"
agent-estimate estimate --format json "Add login button"
agent-estimate validate observation.yaml
agent-estimate validate observation.yaml --db ~/.agent-estimate/calibration.db
agent-estimate calibrate
agent-estimate calibrate --db path/to/db
```

Capture stdout and stderr. If the command exits non-zero, display the error message to the user.

### 4. Display output

Display the CLI output directly to the user. No post-processing — the CLI handles formatting.

## Examples

```
/estimate Add a login page with OAuth
→ agent-estimate estimate "Add a login page with OAuth"

/estimate --file spec.md
→ agent-estimate estimate --file spec.md

/estimate --issues 1,2,3 --repo myorg/myrepo
→ agent-estimate estimate --issues 1,2,3 --repo myorg/myrepo

/estimate --config agents.yaml --format json "Refactor auth module"
→ agent-estimate estimate --config agents.yaml --format json "Refactor auth module"

/validate-estimate results/sprint1.yaml
→ agent-estimate validate results/sprint1.yaml

/validate-estimate results/sprint1.yaml --db ~/.agent-estimate/calibration.db
→ agent-estimate validate results/sprint1.yaml --db ~/.agent-estimate/calibration.db

/calibrate
→ agent-estimate calibrate
```

## Observation YAML format (for `/validate-estimate`)

```yaml
task_type: feature
estimated_minutes: 45.0
actual_work_minutes: 52.0
actual_total_minutes: 60.0
file_count: 3
line_count: 120
test_count: 5
execution_mode: single
review_mode: standard
review_overhead_minutes: 8.0
modifiers:
  spec_clarity: 1.0
  warm_context: 0.9
```

## Notes

- Requires `agent-estimate` installed: `pip install agent-estimate` or `pip install -e .[dev]` in the repo.
- Default config uses bundled `default_agents.yaml`. Pass `--config` to override agent definitions.
- `--review-mode` defaults to `standard` (15 m additive; clean 2x-LGTM). Use `complex` (25 m) for involved or security-sensitive review, `3-round` (35 m) for explicit 3-round cross-agent review, or `none` for self-merge workflows.
- JSON output is available via `--format json`.
- METR p80 reliability thresholds back the over-threshold warnings. Current model keys: `opus_4_7` (Opus 4.7, 90 m), `gpt_5_5` (90 m), `gpt_5_4` (60 m), `gemini_3_1_pro` (45 m), `sonnet_4_6` (30 m), `haiku_4_5` (15 m). `opus_4_x` is a forward-compatible Opus alias; legacy keys (`opus_4_6`, `opus`, `gpt_5`/`5.2`/`5.3`, `gemini_3_pro`, `sonnet`) remain accepted.
