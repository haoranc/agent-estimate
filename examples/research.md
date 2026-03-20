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
| **Audit cloud infrastructure providers for production deployment** | research | S | Claude | 10m / 20m / 30m (E=20m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 20m | 99m |

### Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 27.1m |
| Expected case | 38m |
| Worst case | 48.9m |
| Human-speed equivalent | 99m |
| Compression ratio | 2.61x |
| Review overhead (per-task, pre-amortization) | 15m |

### Agent Load Summary

| Agent | Task Count | Total Work | Estimated Cost |
| --- | --- | --- | --- |
| Claude | 1 | 23m | $0.55 |

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

Research tasks have the highest human-multiplier range (3.0-6.0x) because pattern matching across large datasets is tedious for humans but routine for agents. Scanning 7 cloud providers' pricing, compliance, and feature matrices would take a human most of a workday. Use `--type research` to select the research estimation model — it uses a flat PERT curve with depth scaling instead of the tier-based coding model.
