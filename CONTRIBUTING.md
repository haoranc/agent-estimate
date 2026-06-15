# Contributing to agent-estimate

Thanks for your interest in contributing.

## Ground Rules

- Be respectful and collaborative.
- Follow the [Code of Conduct](./CODE_OF_CONDUCT.md).
- Keep changes focused and well-tested.

## Development Setup

Requirements:

- Python 3.10+
- Git

Setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Windows PowerShell activation:

```powershell
.venv\\Scripts\\Activate.ps1
```

## Local Validation

Run before opening a pull request:

```bash
ruff check .
pytest -q
```

If your change touches CLI behavior, include at least one integration-style test update in `tests/integration/` when appropriate.

## Pull Request Workflow

1. Fork the repository and branch from `main`.
2. Keep PRs scoped to one problem.
3. Link related issue(s) in the PR description.
4. Include a short test plan and validation output.
5. Update docs/changelog when behavior changes.

## Release Checklist

1. Bump all versioned artifacts together: `pyproject.toml`, `src/agent_estimate/version.py`, `.claude-plugin/plugin.json`, `action.yml`, issue templates, and version tests.
2. Run `ruff check .`, `pytest -q`, `python -m build`, and any release-specific smoke tests.
3. Publish the GitHub release and PyPI artifacts.
4. From the `kiloloop/agent-estimate` public clone, move the floating public Action tag, for example `git tag -f v0 vX.Y.Z && git push origin v0 --force`, so `uses: kiloloop/agent-estimate@v0` tracks the latest compatible release. Do not perform this step from the private staging clone.
5. Confirm README, examples, and skill docs match the released CLI output and model keys.

## Reporting Bugs

Use the bug report issue template and include:

- Expected behavior
- Actual behavior
- Minimal reproduction steps
- Python version, OS, and package version

## Proposing Features

Use the feature request template and explain:

- Problem statement
- Proposed solution
- Alternatives considered
- Potential tradeoffs

## Security

For security disclosures, follow [SECURITY.md](./SECURITY.md) and use private reporting.
