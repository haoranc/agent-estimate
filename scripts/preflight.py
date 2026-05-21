#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kiloloop
# SPDX-License-Identifier: Apache-2.0
"""Unified preflight checks for agent-estimate.

Fast mode (default):
- Merge conflict marker scan
- YAML syntax validation for src/ and tests/fixtures/
- `ruff` on all tracked Python files

Extended mode (`--full`): fast mode + `pytest`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

Runner = Callable[[Sequence[str], Path], Tuple[int, str]]
YamlLoader = Callable[[str], object]

MARKER_PREFIXES = ("<<<<<<<", "=======", ">>>>>>>")
YAML_EXTENSIONS = {".yaml", ".yml"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "dist"}


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    duration_s: float

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


def run_command(command: Sequence[str], cwd: Path) -> Tuple[int, str]:
    """Run a command and return (exit_code, combined_output)."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, f"Command not found: {command[0]}"

    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return completed.returncode, combined.strip()


def _discover_repo_files(repo_root: Path, runner: Runner) -> List[Path]:
    rc, output = runner(["git", "ls-files"], repo_root)
    if rc == 0:
        files: List[Path] = []
        for rel in output.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            path = repo_root / rel
            if path.is_file():
                files.append(path)
        return files

    # Fallback for non-git environments.
    files = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(repo_root).parts):
            continue
        files.append(path)
    return files


def check_conflict_markers(repo_root: Path, runner: Runner = run_command) -> CheckResult:
    start = time.monotonic()
    hits: List[str] = []

    for file_path in _discover_repo_files(repo_root, runner):
        rel = file_path.relative_to(repo_root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        try:
            raw = file_path.read_bytes()
        except OSError:
            continue

        if b"\x00" in raw:
            continue

        for lineno, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), start=1):
            stripped = line.strip()
            if (
                stripped.startswith(MARKER_PREFIXES[0])
                or stripped == MARKER_PREFIXES[1]
                or stripped.startswith(MARKER_PREFIXES[2])
            ):
                preview = stripped[:60]
                hits.append(f"{rel}:{lineno}: {preview}")
                if len(hits) >= 20:
                    break
        if len(hits) >= 20:
            break

    if hits:
        shown = "\n".join(hits[:10])
        extra = "" if len(hits) <= 10 else f"\n... and {len(hits) - 10} more"
        return CheckResult(
            name="conflict-markers",
            passed=False,
            details=f"merge conflict markers found:\n{shown}{extra}",
            duration_s=time.monotonic() - start,
        )

    return CheckResult(
        name="conflict-markers",
        passed=True,
        details="no merge conflict markers detected",
        duration_s=time.monotonic() - start,
    )


def default_yaml_loader() -> Optional[YamlLoader]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    return yaml.safe_load


def check_yaml_syntax(repo_root: Path, loader: Optional[YamlLoader] = None) -> CheckResult:
    start = time.monotonic()
    yaml_files: List[Path] = []
    for rel_root in ("src", "tests/fixtures"):
        root = repo_root / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in YAML_EXTENSIONS:
                yaml_files.append(path)
    # Also check root-level YAML files.
    for path in sorted(repo_root.glob("*.yaml")):
        if path.is_file():
            yaml_files.append(path)

    if not yaml_files:
        return CheckResult(
            name="yaml-validate",
            passed=True,
            details="no YAML files found",
            duration_s=time.monotonic() - start,
        )

    yaml_loader = loader or default_yaml_loader()
    if yaml_loader is None:
        return CheckResult(
            name="yaml-validate",
            passed=False,
            details="PyYAML is required for YAML validation (install with `pip install pyyaml`)",
            duration_s=time.monotonic() - start,
        )

    errors: List[str] = []
    for path in yaml_files:
        rel = path.relative_to(repo_root)
        try:
            text = path.read_text(encoding="utf-8")
            yaml_loader(text)
        except Exception as exc:
            errors.append(f"{rel}: {exc}")

    if errors:
        shown = "\n".join(errors[:10])
        extra = "" if len(errors) <= 10 else f"\n... and {len(errors) - 10} more"
        return CheckResult(
            name="yaml-validate",
            passed=False,
            details=f"invalid YAML detected:\n{shown}{extra}",
            duration_s=time.monotonic() - start,
        )

    return CheckResult(
        name="yaml-validate",
        passed=True,
        details=f"validated {len(yaml_files)} YAML files",
        duration_s=time.monotonic() - start,
    )


def _run_external_check(
    *,
    name: str,
    command: Sequence[str],
    repo_root: Path,
    runner: Runner,
) -> CheckResult:
    start = time.monotonic()
    tool = command[0]
    if shutil.which(tool) is None:
        return CheckResult(
            name=name,
            passed=False,
            details=f"{tool} is not on PATH",
            duration_s=time.monotonic() - start,
        )

    rc, output = runner(command, repo_root)
    if rc == 0:
        return CheckResult(
            name=name,
            passed=True,
            details="ok",
            duration_s=time.monotonic() - start,
        )

    details = output or f"{tool} exited with code {rc}"
    return CheckResult(
        name=name,
        passed=False,
        details=details,
        duration_s=time.monotonic() - start,
    )


def check_ruff(repo_root: Path, runner: Runner = run_command) -> CheckResult:
    return _run_external_check(
        name="ruff",
        command=["ruff", "check", "."],
        repo_root=repo_root,
        runner=runner,
    )


def check_tests(repo_root: Path, runner: Runner = run_command) -> CheckResult:
    return _run_external_check(
        name="tests",
        command=["python3", "-m", "pytest", "tests/", "-x", "-q"],
        repo_root=repo_root,
        runner=runner,
    )


def run_preflight(
    repo_root: Path,
    *,
    full: bool,
    runner: Runner = run_command,
    yaml_loader: Optional[YamlLoader] = None,
) -> List[CheckResult]:
    results = [
        check_conflict_markers(repo_root, runner=runner),
        check_yaml_syntax(repo_root, loader=yaml_loader),
        check_ruff(repo_root, runner=runner),
    ]

    if full:
        results.append(check_tests(repo_root, runner=runner))

    return results


def print_report(results: Sequence[CheckResult], *, full: bool) -> None:
    mode = "extended" if full else "fast"
    print(f"Preflight mode: {mode}")

    for result in results:
        print(f"[{result.status}] {result.name} ({result.duration_s:.2f}s)")
        if result.details and result.details != "ok":
            for line in result.details.splitlines():
                print(f"  {line}")

    failures = [result for result in results if not result.passed]
    if failures:
        print(f"\nPreflight FAILED ({len(failures)} check(s) failed).")
    else:
        print("\nPreflight PASSED.")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unified preflight checks.")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository root to validate (default: repo containing this script).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run extended mode (includes pytest).",
    )
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"Repository root not found: {repo_root}", file=sys.stderr)
        return 2

    results = run_preflight(repo_root, full=bool(args.full))
    print_report(results, full=bool(args.full))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
