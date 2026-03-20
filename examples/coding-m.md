# Coding — Medium (M tier)

> Based on a real task from a production multi-agent workflow.

## Command

```bash
agent-estimate estimate "Implement add-agent CLI command with SPEC.md generation"
```

## Output

### Per-Task Estimates

| Task | Model | Tier | Agent | Base PERT (O/M/P) | Modifiers | Effective Duration | Human Equivalent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Implement add-agent CLI command with SPEC.md generation** | coding | M | Claude | 25m / 50m / 90m (E=52.5m) | spec 1.00 x warm 1.00 x fit 1.00 = 1.00 | 52.5m | 190.9m |

### Timeline Summary

| Metric | Value |
| --- | --- |
| Best case | 44.7m |
| Expected case | 75.4m |
| Worst case | 117.2m |
| Human-speed equivalent | 190.9m |
| Compression ratio | 2.53x |
| Review overhead (per-task, pre-amortization) | 15m |

### Agent Load Summary

| Agent | Task Count | Total Work | Estimated Cost |
| --- | --- | --- | --- |
| Claude | 1 | 60.4m | $1.45 |

No METR threshold warnings.

## With modifiers — vague spec, cold context

When the spec is underspecified or the agent lacks prior context for the codebase, modifiers above 1.0 stretch the estimate:

```bash
agent-estimate estimate "Implement add-agent CLI command with SPEC.md generation" \
  --spec-clarity 1.2 --warm-context 1.1
```

| Metric | Default | With modifiers |
| --- | --- | --- |
| Modifiers | spec 1.00 × warm 1.00 = 1.00 | spec 1.20 × warm 1.10 = 1.32 |
| Effective Duration | 52.5m | 69.3m |
| Expected case | 75.4m | 94.7m |
| Estimated cost | $1.45 | $1.91 |

Modifier scale: `spec_clarity` ranges from 0.3 (crystal clear with design doc) to 1.3 (vague one-liner). `warm_context` ranges from 0.3 (agent just finished related work) to 1.15 (cold start, new domain). Values above 1.0 mean harder conditions, values below 1.0 mean easier.

## What actually happened

| Metric | Estimated | Actual |
| --- | --- | --- |
| Agent | Claude | Claude |
| Duration | 75.4m expected | ~90m total (49m work + review rounds) |
| Review | 1 round assumed | 2 rounds (R1 feedback → R2 LGTM) |
| Outcome | — | PR merged, 55 tests added |

The task ran slightly over the expected case due to a second review round. This is exactly the kind of variance PERT captures: the actual (90m) fell between expected (75m) and worst case (117m). In our calibration dataset, the expected case tracks within ±20% for M-tier tasks.

## Key takeaway

M-tier tasks are the most common dispatch target — complex enough to justify agent overhead, predictable enough for reliable estimation. The 2.53x compression means a feature that takes a human developer ~3 hours lands in ~75 minutes of wall clock time.
