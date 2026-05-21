# estimate

PERT three-point estimation with METR reliability thresholds and wave planning for AI agent tasks.

## Overview

Wraps the `agent-estimate` CLI to provide effort estimation, observation validation, and calibration from within an agent runtime. The skill maps user intent to CLI subcommands (`estimate`, `validate`, `calibrate`) and returns output directly.

## Prerequisites

- `agent-estimate` installed: `pip install agent-estimate` or `pip install -e '.[dev]'` in the repo
- Default config uses bundled `default_agents.yaml`; pass `--config` to override

## Runtimes

- **Claude Code**: Install to `.claude/skills/estimate/SKILL.md`
- **Codex**: Install to `.codex/skills/estimate/SKILL.md`

## Install

```bash
# Claude Code
mkdir -p .claude/skills/estimate
cp skills/estimate/claude/SKILL.md .claude/skills/estimate/SKILL.md

# Codex
mkdir -p .codex/skills/estimate
cp skills/estimate/codex/SKILL.md .codex/skills/estimate/SKILL.md
```

## Usage

```bash
# Claude Code
/estimate Add a login page with OAuth
/estimate --file tasks.md
/estimate --issues 1,2,3 --repo myorg/myrepo
/validate-estimate observation.yaml
/calibrate

# Codex
# Invoke via AGENTS.md task dispatch or direct skill reference
agent-estimate estimate "Add a login page with OAuth"
agent-estimate validate observation.yaml
agent-estimate calibrate
```
