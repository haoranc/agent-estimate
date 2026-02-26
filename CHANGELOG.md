# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-02-26

### Changed
- Relicensed the project from MIT to Apache License 2.0; added `NOTICE` and updated license metadata across package and plugin artifacts. (#73)

## [0.3.0] - 2026-02-23

### Added
- GitHub Action for CI/CD estimation (`uses: haoranc/agent-estimate@v0`). Supports job summary, PR comments, and step outputs. (#67)

## [0.2.0] - 2026-02-21

### Changed
- Review overhead model is now additive (0m / 15m / 25m) instead of percentage-based. ReviewMode values: `none`, `standard`, `complex`. Legacy `self` and `2x-lgtm` still accepted for backwards compatibility. (#46)

### Added
- Tier auto-correction heuristics: auto-upgrades to L when scope signals exceed thresholds (tests > 20, lines > 200, concerns >= 3) and auto-downgrades to XS for trivial tasks. `--no-auto-tier` flag to disable. (#47)
- Co-dispatch warm context: when 2+ tasks target the same agent in one wave, auto-applies 0.5x warm context duration reduction to tasks beyond the first. (#48)
- Modifier product floor of 0.10 to prevent sub-10m pathology when modifiers stack aggressively. Warning logged when floor fires. (#50)
- Batch wave estimation: amortizes review overhead across same-agent tasks per wave — single review cycle per agent instead of per task. `TaskNode.review_minutes` separates review from work duration. (#49)
- Non-coding task type estimation: `--type` flag for brainstorm, research, config, and documentation tasks with category-specific models. Auto-detection heuristic from description keywords. (#55)
- Multi-agent session estimation: `agent-estimate session` subcommand for coordinated workflows. Wall-clock vs agent-minutes distinction with `--agents`, `--rounds`, `--type` flags. (#56)

### Fixed
- 11 post-LGTM nits from ae-task-models blitz: fractional minute rounding, deterministic wave tie-breaking, tightened keyword patterns, parallel efficiency calculation, and JSON report completeness. (#63)

## [0.1.0] - 2026-02-18

### Added
- PERT three-point estimation engine
- METR per-model reliability thresholds with modifier floors
- Dependency-aware wave planner for multi-agent parallel execution
- Review overhead modes: none, self, 2x-lgtm
- CLI commands: estimate, validate, calibrate
- GitHub issue ingestion via REST API and gh CLI
- Markdown and JSON report renderers
- SQLite calibration store
- Claude Code plugin skill (`/estimate`)
- Warm context auto-detection from dispatch history
- Modifier flags: `--warm-context`, `--spec-clarity`, `--issues`
- PyPI package: `pip install agent-estimate`

[0.4.0]: https://github.com/haoranc/agent-estimate/releases/tag/v0.4.0
[0.3.0]: https://github.com/haoranc/agent-estimate/releases/tag/v0.3.0
[0.2.0]: https://github.com/haoranc/agent-estimate/releases/tag/v0.2.0
[0.1.0]: https://github.com/haoranc/agent-estimate/releases/tag/v0.1.0
