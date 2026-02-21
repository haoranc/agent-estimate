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
| `--review-mode <mode>` |       | Review overhead tier: `none` (0 m), `standard` (15 m, default), `complex` (25 m) |
| `--issues <nums>`      | `-i`  | Comma-separated GitHub issue numbers                 |
| `--repo <owner/name>`  | `-r`  | GitHub repo (required with `--issues`)               |
| `--title <text>`       | `-t`  | Report title                                         |

If none of `--file`, `--issues`, or a task description is provided, prompt the user:
> Please provide a task description, `--file <path>`, or `--issues <nums> --repo <owner/name>`.

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
- `--review-mode` defaults to `standard` (15 m additive; clean 2x-LGTM). Use `complex` for 3+ review rounds. Use `none` for self-merge workflows.
- JSON output is available via `--format json`.
