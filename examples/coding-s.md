# Coding — Small (XS tier)

> Based on a real task from a production multi-agent workflow.

## Command

```bash
agent-estimate estimate "Fix pyproject.toml URLs after org rename"
```

## Output

### Per-Task Estimates

| Task | Model | Tier | Agent | Base PERT (O/M/P) | Modifiers | Effective Duration | Human Equivalent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Fix pyproject.toml URLs after org rename** | coding | XS | Claude | 5m / 10m / 20m (E=10.8m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 10.8m | 54.8m |

### Wave Plan

| Wave | Tasks | Duration | Agent Assignments (amortized review) |
| --- | --- | --- | --- |
| 0 | Fix pyproject.toml URLs after org rename | 27.5m | Claude: Fix pyproject.toml URLs after org rename +15m review |

### Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 21.3m |
| Expected case | 27.5m |
| Worst case | 37.2m |
| Human-speed equivalent | 54.8m |
| Compression ratio | 2.00x |
| Review overhead (per-task, pre-amortization) | 15m |

### Review Overhead

Review is amortized per agent per wave: one review cycle covers all PRs from that
agent in the wave.  Per-task values below are the naive (pre-amortization) figures.

| Task | Review Overhead |
| --- | --- |
| Fix pyproject.toml URLs after org rename | 15m |
| **Total (naive)** | **15m** |

### Agent Load Summary

| Agent | Task Count | Total Work | Estimated Cost |
| --- | --- | --- | --- |
| Claude | 1 | 12.5m | $0.30 |
| Codex | 0 | 0m | $0.00 |
| Gemini | 0 | 0m | $0.00 |

### Critical Path

**Fix pyproject.toml URLs after org rename**

### Tier Corrections

No tier corrections.

### METR Warnings

No METR threshold warnings.


## What actually happened

| Metric | Estimated | Actual |
| --- | --- | --- |
| Agent | Claude | Codex |
| Duration | 27.5m expected | ~25m |
| Outcome | — | PR merged, 11 files updated |

The task was dispatched to Codex (better fit for mechanical find-and-replace across many files). Finished within the estimate window. XS tasks like this are the bread and butter of agent dispatch — low risk, predictable, and the 2x compression adds up across dozens of small tasks per week.

> These results come from a calibrated dataset of 190+ real agent dispatches.

## Key takeaway

XS tasks have a lower compression ratio (2.00x) because the fixed 15m review overhead dominates. For self-merged work where you trust the agent, use `--review-mode none` to remove the review overhead: an executed none-mode run keeps effective duration at 10.8m, drops expected case to 12.5m, and scales human-equivalent time down to 23m human time, for 1.84x compression. Human-equivalent time scales with the agent total, so removing review lowers both sides of the comparison and keeps roughly the same ~2x compression ratio instead of creating a 5x raw-speed claim.
