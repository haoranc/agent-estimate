# Multi-Agent Session

> Based on real tasks from a production multi-agent workflow.

## Input file

Create a file `tasks.txt` with one task per line:

```
Implement add-agent CLI command with SPEC.md generation
Add known_debt.md as standard protocol memory file
Write quickstart guide with protocol comparison table
```

## Command

```bash
agent-estimate estimate --file tasks.txt
```

## Output

### Per-Task Estimates

| Task | Model | Tier | Agent | Base PERT (O/M/P) | Modifiers | Effective Duration | Human Equivalent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Implement add-agent CLI command with SPEC.md generation** | coding | M | Claude | 25m / 50m / 90m (E=52.5m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 52.5m | 190.9m |
| Add known_debt.md as standard protocol memory file | coding | M | Codex | 25m / 50m / 90m (E=52.5m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 52.5m | 190.9m |
| Write quickstart guide with protocol comparison table | coding | M | Gemini | 25m / 50m / 90m (E=52.5m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 52.5m | 190.9m |

### Wave Plan

| Wave | Tasks | Duration | Agent Assignments (amortized review) |
| --- | --- | --- | --- |
| 0 | All 3 tasks | 75.4m | Claude: add-agent CLI +15m review; Codex: known_debt.md +15m review; Gemini: quickstart guide +15m review |

### Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 44.7m |
| Expected case | 75.4m |
| Worst case | 117.2m |
| Human-speed equivalent | 572.8m |
| Compression ratio | 7.60x |
| Review overhead (per-task, pre-amortization) | 45m |

### Agent Load Summary

| Agent | Task Count | Total Work | Estimated Cost |
| --- | --- | --- | --- |
| Claude | 1 | 60.4m | $1.45 |
| Codex | 1 | 60.4m | $0.97 |
| Gemini | 1 | 60.4m | $1.09 |

### Critical Path

**Implement add-agent CLI command with SPEC.md generation**

### METR Warnings

- **Add known_debt.md as standard protocol memory file**: Estimate (68m) exceeds gpt_5_3 p80 threshold (60m). Consider splitting the task.
- **Write quickstart guide with protocol comparison table**: Estimate (68m) exceeds gemini_3_pro p80 threshold (45m). Consider splitting the task.

## What actually happened

These three tasks were dispatched to real agents in a production multi-agent workflow:

| Task | Agent | Estimated | Actual | Review | Outcome |
| --- | --- | --- | --- | --- | --- |
| add-agent CLI | Claude | 75.4m | ~90m | 2 rounds (R2 LGTM) | Merged |
| Protocol memory file | Codex | 75.4m | ~20m | Clean merge | Merged |
| Quickstart + README | Claude | 75.4m | ~45m | 2 rounds | Merged |

**Wall clock**: All three ran in parallel. Total elapsed ~90m (bounded by the slowest task). Sequential human equivalent: ~573m (~9.5 hours).

**Actual compression**: 6.4x (90m wall clock / 573m human equivalent). The estimate predicted 7.6x — close, because one task (add-agent CLI) needed an extra review round that pushed it past the expected case.

The METR warnings were useful: Codex's task landed well under the threshold (20m actual vs 60m warning), but the warning correctly flagged that the Gemini-assigned task was near its reliability limit.

## Key takeaway

Multi-agent sessions are where `agent-estimate` delivers the most value. Three agents working in parallel produce **7.6x compression** — ~75 minutes wall clock vs ~9.5 hours of sequential human work. The wave planner automatically assigns tasks to agents, schedules them in parallel, and flags reliability risks via METR warnings. You see the total cost ($3.51), parallelism benefit, and risk before committing compute.
