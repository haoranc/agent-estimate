# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Review overhead model is now additive (0m / 15m / 25m) instead of percentage-based. ReviewMode values: `none`, `standard`, `complex`. Legacy `self` and `2x-lgtm` still accepted for backwards compatibility. (#46)

### Added
- Tier auto-correction heuristics: auto-upgrades to L when scope signals exceed thresholds (tests > 20, lines > 200, concerns >= 3) and auto-downgrades to XS for trivial tasks. `--no-auto-tier` flag to disable. (#47)
- Co-dispatch warm context: when 2+ tasks target the same agent in one wave, auto-applies 0.5x warm context duration reduction to tasks beyond the first. (#48)

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

[0.1.0]: https://github.com/haoranc/agent-estimate/releases/tag/v0.1.0

