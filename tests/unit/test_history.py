"""Unit tests for dispatch history loading and warm_context inference."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_estimate.core.history import infer_warm_context


@pytest.fixture()
def ref_time() -> datetime:
    """Fixed reference time for deterministic tests."""
    return datetime(2026, 2, 19, 9, 0, 0, tzinfo=timezone.utc)


def _write_history(tmp_path: Path, dispatches: list[dict]) -> Path:
    """Write a dispatch history JSON file and return its path."""
    p = tmp_path / "history.json"
    p.write_text(json.dumps({"dispatches": dispatches}), encoding="utf-8")
    return p


# --- Decay band tests ---


def test_recent_dispatch_returns_03(tmp_path: Path, ref_time: datetime) -> None:
    """Dispatch <2h ago -> 0.3."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(minutes=8)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, reference_time=ref_time)
    assert result.value == 0.3
    assert result.source == "auto"
    assert "8m ago" in result.detail


def test_medium_dispatch_returns_05(tmp_path: Path, ref_time: datetime) -> None:
    """Dispatch 2-12h ago -> 0.5."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(hours=6)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, reference_time=ref_time)
    assert result.value == 0.5
    assert result.source == "auto"


def test_old_dispatch_returns_07(tmp_path: Path, ref_time: datetime) -> None:
    """Dispatch 12-24h ago -> 0.7."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(hours=18)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, reference_time=ref_time)
    assert result.value == 0.7
    assert result.source == "auto"


def test_stale_dispatch_returns_10(tmp_path: Path, ref_time: datetime) -> None:
    """Dispatch >24h ago -> 1.0."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(hours=48)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, reference_time=ref_time)
    assert result.value == 1.0
    assert result.source == "auto"


# --- Filtering tests ---


def test_no_matching_agent_returns_10(tmp_path: Path, ref_time: datetime) -> None:
    """Filter by agent with no match -> 1.0."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(minutes=5)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, agent="gemini", reference_time=ref_time)
    assert result.value == 1.0
    assert result.source == "default"


def test_no_matching_project_returns_10(tmp_path: Path, ref_time: datetime) -> None:
    """Filter by project with no match -> 1.0."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(minutes=5)).isoformat(),
        }
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, project="other-project", reference_time=ref_time)
    assert result.value == 1.0
    assert result.source == "default"


# --- Error handling tests ---


def test_missing_file_returns_10_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing file -> 1.0 with warning logged."""
    path = tmp_path / "nonexistent.json"
    with caplog.at_level(logging.WARNING, logger="agent_estimate"):
        result = infer_warm_context(path)
    assert result.value == 1.0
    assert result.source == "default"
    assert "not found" in caplog.text


def test_malformed_json_returns_10_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Malformed JSON -> 1.0 with warning logged."""
    path = tmp_path / "bad.json"
    path.write_text("{invalid json", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="agent_estimate"):
        result = infer_warm_context(path)
    assert result.value == 1.0
    assert result.source == "default"
    assert "Malformed JSON" in caplog.text


def test_missing_dispatches_key_returns_10(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """JSON without 'dispatches' key -> 1.0 with warning."""
    path = tmp_path / "no_key.json"
    path.write_text('{"other": []}', encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="agent_estimate"):
        result = infer_warm_context(path)
    assert result.value == 1.0
    assert result.source == "default"
    assert "missing 'dispatches' key" in caplog.text


# --- Multi-dispatch tests ---


def test_multiple_dispatches_uses_most_recent(
    tmp_path: Path, ref_time: datetime
) -> None:
    """When multiple dispatches match, the most recent one is used."""
    dispatches = [
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(hours=18)).isoformat(),
            "task": "old task",
        },
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(minutes=30)).isoformat(),
            "task": "recent task",
        },
        {
            "agent": "codex",
            "project": "agent-estimate",
            "completed_at": (ref_time - timedelta(hours=6)).isoformat(),
            "task": "medium task",
        },
    ]
    path = _write_history(tmp_path, dispatches)
    result = infer_warm_context(path, reference_time=ref_time)
    # Most recent is 30m ago -> 0.3
    assert result.value == 0.3
    assert result.source == "auto"


# --- None path test ---


def test_none_path_returns_default() -> None:
    """None path -> default 1.0."""
    result = infer_warm_context(None)
    assert result.value == 1.0
    assert result.source == "default"
