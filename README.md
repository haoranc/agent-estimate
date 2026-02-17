# agent-estimate

The first open-source effort estimation tool built for AI coding agents.

Not story points. Not human-hours. Wall-clock time for multi-agent parallel execution.

## Why

Every team using Claude Code, Codex, Cursor, or similar AI coding agents needs a way to estimate how long agent-driven work will take. The current answer is "guess." We replace that with a calibrated, methodology-backed tool.

## What It Does

- **PERT for AI agents** — three-point estimation (Optimistic / Most Likely / Pessimistic) adapted for AI agent task types
- **METR-aware** — flags tasks exceeding the reliable-completion threshold for the target model
- **Wave planning** — dependency-aware parallel scheduling across multi-agent fleets
- **Self-calibrating** — tracks estimated vs actual completion times, auto-adjusts defaults

## Quick Start

```bash
pip install agent-estimate

# Estimate from a description
agent-estimate "Build a REST API with auth and role-based access control"

# Estimate from GitHub issues
agent-estimate --issues 119,122,125 --repo myorg/myrepo

# Estimate from a spec file
agent-estimate --file docs/mvp-spec.md

# Custom agent fleet
agent-estimate --config agents.yaml "Build a REST API"
```

## Agent Config

```yaml
agents:
  - name: claude
    capabilities: [reasoning, orchestration, refactoring, architecture]
    parallelism: 1
    model_tier: heavy
  - name: codex
    capabilities: [shell, patching, config, scripts, crud]
    parallelism: 1
    model_tier: standard

settings:
  friction_multiplier: 1.15
  inter_wave_overhead: 15  # minutes between waves
  review_overhead: 0.10    # 10% for self-review
```

## Status

**Pre-release** — architecture designed, implementation starting. See [project plan](https://github.com/haoranc/agent-estimate/blob/main/docs/project_plan.md) for details.

## License

MIT
