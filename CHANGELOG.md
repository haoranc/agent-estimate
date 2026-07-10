# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.3] - 2026-07-10

### Fixed
- `agent-estimate validate` now reports a clean user-facing error instead of a traceback when calibration DB observation fields have invalid types, with end-to-end tests covering the calibration write path.
- Refreshed shipped example outputs for current engine numbers and expanded docs freshness tests to cover every example capture.

## [0.7.2] - 2026-06-14

### Fixed
- Fixed engine and documentation correctness gaps: documentation estimates now use the docs human multiplier, CLI file/config and GitHub adapter failures stay user-facing, REST issue ingestion is reachable in token-only environments, renderer warning/detail fields are escaped and serialized, sizing heuristics prefer explicit test/docs matches, store/audit/validation edge cases are hardened, and stale skill/session/release docs are refreshed (#30, #32, #34, #35, #41, #42, #43, #44, #45).
- `AGENT_ESTIMATE_AUDIT_DESTINATION=stdout` now emits a deprecation warning and routes audit events to stderr so report stdout remains parseable for JSON consumers (#43).

## [0.7.1] - 2026-06-11

### Fixed
- Fixed six engine correctness gaps: early `--format` validation before side effects, explicit `--warm-context 1.0` handling, friction-aware assigned-agent METR re-checks, Python 3.10-compatible Z timestamp parsing, UTC-normalized calibration cohorts/order, and `plan_waves` duplicate/negative input validation (#31, #33, #36, #37, #38, #39).
- README hero example now uses the real CLI surface with real captured output — the previous block invoked a nonexistent `--model` flag, passed an unsupported second positional task, and showed fabricated numbers (#28).
- README Action workflow example now grants `issues: read`, required for issue fetching on private repos where an explicit `permissions:` block zeroes unlisted scopes (#40).
- Claude Code plugin exposes the `/estimate` skill again: `plugin.json` now points skill discovery at `skills/estimate/claude/`, which the v0.7.0 multi-runtime restructure had moved out of the default `skills/<name>/SKILL.md` scan path (#29).
- Dropped the phantom `/validate-estimate` and `/calibrate` slash commands (documented but never installable); validation and calibration now route through the installed skill as `/estimate validate` and `/estimate calibrate` (#29).
- Refreshed stale METR model keys in `examples/multi-agent.md` output (`gpt_5_3` → `gpt_5_4`, `gemini_3_pro` → `gemini_3_1_pro`) to match current output (#28).

## [0.7.0] - 2026-05-20

### Added
- Frontend/UI task category with separate content-patch (15/25/40) and page-build (40/60/90) bands.
- App-development task category with a generic cold L-style prior and app/UI human-comparison multiplier.
- `3-round` review mode with a 35 minute additive review tier.
- METR threshold entries for Opus 4.7 (current) and GPT-5.5; `opus_4_x` retained as a forward-compatible alias.
- Opt-in structured audit logging via `AGENT_ESTIMATE_AUDIT_*` environment variables, emitting secret-scrubbed JSON events to stdout, stderr, or a file.

### Changed
- Research-grounded brainstorms now route to the research band instead of the flat brainstorm band.
- Codex model-key alias now resolves to the GPT-5.5 METR threshold; GPT-5.4 remains available.
- Corrected the Codex skill install path in `skills/estimate/README.md` to `.codex/skills/...`.
- Version bumped to v0.7.0 across package, plugin, action, issue template, and tests.
- Claude runtime `/estimate` skill refreshed to v0.7.0 parity with the Codex slice (frontend/app_dev types, `3-round` review mode, refreshed METR keys).
- `claude`/`claude_opus` model-key aliases now resolve to `opus_4_7` (Opus 4.7); `opus_4_6` retained for backward compatibility.

## [0.6.1] - 2026-03-20

### Fixed
- `--version` CLI flag now reports correct version (was stuck at 0.4.0 due to `version.py` not being updated).
- Synced version across all artifacts: pyproject.toml, version.py, plugin.json, action.yml, bug_report template.

## [0.6.0] - 2026-03-20

### Changed
- README rewritten as a conversion page with real-data hero examples, human-multiplier compression ratios, and curated worked examples.
- Updated METR threshold model fleet: added Opus 4.6 (90m), GPT-5.4 (60m), Gemini 3.1 Pro (45m), Sonnet 4.6 (30m), Haiku 4.5 (15m). Legacy keys preserved.
- Updated model key aliases: `claude`→`opus_4_6`, `codex`→`gpt_5_4`, `gemini`→`gemini_3_1_pro`, `sonnet`→`sonnet_4_6`, `haiku`→`haiku_4_5`.
- Fixed `frontier` model tier resolution to correctly disambiguate by agent name instead of alias short-circuit.
- Updated pyproject.toml description to "Know what an AI task will cost before you run it".

### Added
- `examples/` directory with 5 curated worked examples: coding-s, coding-m, research, documentation, multi-agent.

## [0.5.0] - 2026-03-20

### Changed
- Transferred repo from `haoranc/agent-estimate` to `kiloloop/agent-estimate`; updated all org references in pyproject.toml, README, action.yml, plugin manifests, and community health docs.

### Added
- Privacy policy and support URL for plugin directory verified status. (#75)
- Community health docs: CODE_OF_CONDUCT, CONTRIBUTING, SECURITY, SUPPORT templates. (#76)
- Updated copyright to Kiloloop LLC. (#77)

## [0.4.0] - 2026-02-26

### Changed
- Relicensed the project from MIT to Apache License 2.0; added `NOTICE` and updated license metadata across package and plugin artifacts. (#73)

## [0.3.0] - 2026-02-23

### Added
- GitHub Action for CI/CD estimation (`uses: kiloloop/agent-estimate@v0`). Supports job summary, PR comments, and step outputs. (#67)

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

[0.7.3]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.7.3
[0.7.2]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.7.2
[0.7.1]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.7.1
[0.7.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.7.0
[0.6.1]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.6.1
[0.6.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.6.0
[0.5.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.5.0
[0.4.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.4.0
[0.3.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.3.0
[0.2.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.2.0
[0.1.0]: https://github.com/kiloloop/agent-estimate/releases/tag/v0.1.0
