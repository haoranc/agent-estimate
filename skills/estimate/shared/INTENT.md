# estimate — Shared Intent

## What it does

Wraps the `agent-estimate` CLI to provide PERT three-point effort estimation with METR reliability thresholds and wave planning for AI agent tasks. The skill is command-first: it maps user intent to a CLI subcommand, executes it, and returns the output directly.

## Subcommands

| Intent | Command |
|--------|---------|
| Estimate one or more tasks | `agent-estimate estimate ...` |
| Estimate a multi-agent session | `agent-estimate session ...` |
| Validate estimate vs actuals | `agent-estimate validate <observation.yaml> ...` |
| Recompute calibration summary | `agent-estimate calibrate ...` |

## CLI flags

### `estimate`

Accepts exactly one input source:
- Task description as a positional argument
- `--file <path>` — path to task file (one task per line)
- `--issues <nums>` — comma-separated GitHub issue numbers (requires `--repo <owner/name>`)

Optional flags:
- `--config <path>` — path to config YAML with agent definitions
- `--format markdown|json` — output format (default: `markdown`)
- `--review-mode none|standard|complex|3-round` — review overhead tier
- `--type coding|brainstorm|research|config|documentation|frontend|app_dev` — task category; omit to auto-detect
- `--spec-clarity <0.3..1.3>` — spec clarity modifier
- `--warm-context <0.3..1.15>` — warm context modifier
- `--agent-fit <0.9..1.2>` — agent fit modifier
- `--title <text>` — report title
- `--verbose` — enable debug logging

If no input source is provided, prompt the user.

### `session`

- `--agents <n>` — number of parallel agents
- `--rounds <n>` — number of sequential rounds
- `--type brainstorm|review|research|documentation|config|coding` — session task type
- `--coordination-overhead <minutes>` — per-round coordination overhead
- `--per-round-minutes <minutes>` — explicit per-agent round duration
- `--format markdown|json` — output format

### `validate`

- Required: observation YAML path
- Optional: `--db <path>`

### `calibrate`

- Optional: `--db <path>` (default: `~/.agent-estimate/calibration.db`)

## Observation YAML format

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

## Acceptance criteria

- CLI command is constructed correctly from user input
- Command is executed and stdout/stderr captured
- On success, CLI output is returned directly (no post-processing)
- On failure, error message and attempted command are shown
- JSON output (`--format json`) is a normal success path
