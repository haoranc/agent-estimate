# Research

> Based on a real task from a production multi-agent workflow.

## Command

```bash
agent-estimate estimate \
  "Audit cloud infrastructure providers for production deployment" \
  --type research
```

## Output

### Per-Task Estimates

| Task | Model | Tier | Agent | Base PERT (O/M/P) | Modifiers | Effective Duration | Human Equivalent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Audit cloud infrastructure providers for production deploym…** | research | S | Claude | 10m / 20m / 30m (E=20m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 20m | 99m |

### Wave Plan

| Wave | Tasks | Duration | Agent Assignments (amortized review) |
| --- | --- | --- | --- |
| 0 | Audit cloud infrastructure providers for production deploym… | 38m | Claude: Audit cloud infrastructure providers for production deploym… +15m review |

### Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 27.1m |
| Expected case | 38m |
| Worst case | 48.9m |
| Human-speed equivalent | 99m |
| Compression ratio | 2.61x |
| Review overhead (per-task, pre-amortization) | 15m |

### Review Overhead

Review is amortized per agent per wave: one review cycle covers all PRs from that
agent in the wave.  Per-task values below are the naive (pre-amortization) figures.

| Task | Review Overhead |
| --- | --- |
| Audit cloud infrastructure providers for production deploym… | 15m |
| **Total (naive)** | **15m** |

### Agent Load Summary

| Agent | Task Count | Total Work | Estimated Cost |
| --- | --- | --- | --- |
| Claude | 1 | 23m | $0.55 |
| Codex | 0 | 0m | $0.00 |
| Gemini | 0 | 0m | $0.00 |

### Critical Path

**Audit cloud infrastructure providers for production deploym…**

### Tier Corrections

No tier corrections.

### METR Warnings

No METR threshold warnings.


## What actually happened

| Metric | Estimated | Actual |
| --- | --- | --- |
| Agent | Claude | Claude |
| Duration | 38m expected | ~15m |
| Outcome | — | 12-section report, 7 providers evaluated, recommended hybrid deployment |
| Quality | — | Q4 (strong) |

The agent finished well under the estimate — research tasks with web access tend to run fast because agents scan documentation and pricing pages in parallel. The actual landed below even the best case (27m). This is typical for research: high variance, but the wins are dramatic.

## Key takeaway

Research tasks use the generic human-multiplier range (2.0-4.0x) while the research model handles the agent-side time box. Pattern matching across large datasets is still tedious for humans but routine for agents: scanning 7 cloud providers' pricing, compliance, and feature matrices would take a human most of a workday. Use `--type research` to select the research estimation model — it uses a flat PERT curve with depth scaling instead of the tier-based coding model.
