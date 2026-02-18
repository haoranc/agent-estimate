"""Unit tests for SQLite calibration store adapter."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from agent_estimate.adapters.sqlite_store import (
    ObservationInput,
    SQLiteCalibrationStore,
    calibrate,
)


@pytest.fixture
def store(tmp_path: Path) -> Generator[SQLiteCalibrationStore, None, None]:
    calibration_store = SQLiteCalibrationStore(tmp_path / "calibration.db")
    yield calibration_store
    calibration_store.close()


def _observation(
    *,
    task_type: str = "feature",
    error_ratio: float = 0.2,
    observed_at: str = "2026-02-16T12:00:00+00:00",
) -> ObservationInput:
    return ObservationInput(
        task_type=task_type,
        estimated_secs=120.0,
        actual_work_secs=140.0,
        actual_total_secs=150.0,
        error_ratio=error_ratio,
        file_count=3,
        line_count=220,
        test_count=4,
        project_hash="proj-123",
        spec_clarity_modifier=0.8,
        warm_context_modifier=0.6,
        execution_mode="sync",
        review_mode="async",
        review_overhead_secs=30.0,
        verdict="pass",
        modifiers_should_have_been={"spec_clarity": 0.75, "warm_context": 0.7},
        observed_at=observed_at,
    )


def test_insert_and_query_observation(store: SQLiteCalibrationStore) -> None:
    observation_id = store.insert_observation(_observation())

    assert observation_id > 0
    assert store.journal_mode() == "wal"

    rows = store._query_observations(task_type="feature")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == observation_id
    assert row["task_type"] == "feature"
    assert row["estimated_secs"] == pytest.approx(120.0)
    assert row["error_ratio"] == pytest.approx(0.2)
    assert json.loads(row["modifiers_should_have_been"])["spec_clarity"] == pytest.approx(0.75)


def test_calibrate_recomputes_weekly_summary(store: SQLiteCalibrationStore) -> None:
    for ratio in [0.10, 0.20, 0.30, 0.40, 0.50]:
        store.insert_observation(_observation(task_type="bugfix", error_ratio=ratio))

    store.calibrate()
    summary_rows = store.query_calibration_summary()

    assert len(summary_rows) == 1
    summary = summary_rows[0]
    assert summary["task_type"] == "bugfix"
    assert summary["sample_count"] == 5
    assert summary["median_error_pct"] == pytest.approx(30.0)
    assert summary["p10"] == pytest.approx(14.0)
    assert summary["p90"] == pytest.approx(46.0)


def test_export_requires_opt_in_and_enforces_k_anonymity(store: SQLiteCalibrationStore) -> None:
    for ratio in [0.1, 0.2, 0.3, 0.4]:
        store.insert_observation(_observation(task_type="small-cohort", error_ratio=ratio))
    for ratio in [0.1, 0.2, 0.3, 0.4, 0.5]:
        store.insert_observation(_observation(task_type="large-cohort", error_ratio=ratio))

    store.calibrate()

    with pytest.raises(PermissionError):
        store.export_calibration_summary()

    exported = store.export_calibration_summary(allow_export=True)
    assert len(exported) == 1
    row = exported[0]
    assert row["task_type"] == "large-cohort"
    assert row["sample_count"] == 5

    # Export stays on aggregate boundary and never leaks raw observation fields.
    assert "estimated_secs" not in row
    assert "project_hash" not in row
    assert "modifiers_should_have_been" not in row


def test_module_level_calibrate_recomputes_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "calibrate.db"
    store = SQLiteCalibrationStore(db_path)
    try:
        store.insert_observation(_observation(task_type="ops", error_ratio=0.25))
        store.insert_observation(_observation(task_type="ops", error_ratio=0.35))
    finally:
        store.close()

    summary_rows = calibrate(db_path)

    assert len(summary_rows) == 1
    assert summary_rows[0]["task_type"] == "ops"
    assert summary_rows[0]["sample_count"] == 2


def test_store_supports_context_manager(tmp_path: Path) -> None:
    db_path = tmp_path / "ctx.db"
    with SQLiteCalibrationStore(db_path) as store:
        store.insert_observation(_observation())

    with SQLiteCalibrationStore(db_path) as store:
        rows = store.query_calibration_summary()
        assert rows == []


def test_schema_version_table_exists(store: SQLiteCalibrationStore) -> None:
    row = store._connection.execute("SELECT version FROM schema_version").fetchone()
    assert row is not None
    assert row["version"] == 1


def test_insert_rejects_invalid_negative_values(store: SQLiteCalibrationStore) -> None:
    invalid = _observation()
    invalid = ObservationInput(
        **{
            **invalid.__dict__,
            "estimated_secs": -1.0,
        },
    )
    with pytest.raises(ValueError, match="estimated_secs must be >= 0"):
        store.insert_observation(invalid)
