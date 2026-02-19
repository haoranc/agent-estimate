# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
