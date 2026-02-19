---
name: estimate
description: Codex skill for running agent-estimate CLI commands (estimate, validate, calibrate).
---

# estimate (Codex)

Use this skill when a user asks to estimate delivery effort for coding work, validate an estimate with observed results, or recalibrate model factors.

The skill is command-first: execute the `agent-estimate` CLI and return its output.

## Intent Mapping

| User intent | Command |
| --- | --- |
| Estimate one task or multiple tasks | `agent-estimate estimate ...` |
| Validate estimate vs actuals | `agent-estimate validate <observation.yaml> ...` |
| Recompute calibration summary | `agent-estimate calibrate ...` |

## Build Rules

### For `estimate`

- Accept exactly one input source:
  - task description argument
  - `--file <path>`
  - `--issues <nums>` (requires `--repo <owner/name>`)
- Supported flags:
  - `--config <path>`
  - `--format markdown|json`
  - `--review-mode none|self|2x-lgtm`
  - `--title <text>`
  - `--verbose`

If input source is missing, ask for one.

### For `validate`

- Required: observation YAML path.
- Optional: `--db <path>`.

### For `calibrate`

- Optional: `--db <path>`.
- Default DB: `~/.agent-estimate/calibration.db`.

## Execution Rules

1. Execute commands from the repository root.
2. Prefer `agent-estimate` binary; fallback to `python -m agent_estimate.cli.app` if needed.
3. Capture stdout/stderr and exit code.
4. If command fails, return the error concisely and include the attempted command.
5. If command succeeds, return CLI output directly.
6. `--format json` is supported and should be treated as a normal success path.

## Command Examples

```bash
agent-estimate estimate "Add login button with OAuth"
agent-estimate estimate --file tasks.md
agent-estimate estimate --issues 1,2,3 --repo org/name
agent-estimate estimate --config agents.yaml --format json "Refactor auth module"
agent-estimate validate observation.yaml --db ~/.agent-estimate/calibration.db
agent-estimate calibrate --db ~/.agent-estimate/calibration.db
```

## Observation YAML Example

```yaml
task_type: feature
estimated_minutes: 45.0
actual_work_minutes: 52.0
actual_total_minutes: 60.0
file_count: 3
line_count: 120
test_count: 5
execution_mode: single
review_mode: 2x-lgtm
review_overhead_minutes: 8.0
modifiers:
  spec_clarity: 1.0
  warm_context: 0.9
```

## Notes

- Requires `agent-estimate` installed: `pip install agent-estimate` or `pip install -e '.[dev]'` in this repo.
- Default config uses bundled `default_agents.yaml`. Pass `--config` to override agent definitions.
- `--review-mode` defaults to `2x-lgtm`.
- Keep command output as source of truth; do not invent computed values.
