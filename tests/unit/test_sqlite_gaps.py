"""Additional SQLite store tests filling coverage gaps."""

from __future__ import annotations

import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from agent_estimate.adapters import sqlite_store
from agent_estimate.adapters.sqlite_store import (
    ObservationInput,
    SQLiteCalibrationStore,
    _percentile,
)


@pytest.fixture
def store(tmp_path: Path) -> Generator[SQLiteCalibrationStore, None, None]:
    calibration_store = SQLiteCalibrationStore(tmp_path / "calibration.db")
    yield calibration_store
    calibration_store.close()


def _observation(**overrides: object) -> ObservationInput:
    base = {
        "task_type": "feature",
        "estimated_secs": 120.0,
        "actual_work_secs": 140.0,
        "actual_total_secs": 150.0,
        "error_ratio": 0.2,
        "file_count": 3,
        "line_count": 220,
        "test_count": 4,
        "project_hash": "proj-123",
        "spec_clarity_modifier": 0.8,
        "warm_context_modifier": 0.6,
        "execution_mode": "sync",
        "review_mode": "async",
        "review_overhead_secs": 30.0,
        "verdict": "pass",
        "modifiers_should_have_been": {"spec_clarity": 0.75},
        "observed_at": "2026-02-16T12:00:00+00:00",
    }
    base.update(overrides)
    return ObservationInput(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _validate_observation — empty strings
# ---------------------------------------------------------------------------


class TestValidateObservationEmptyStrings:
    def test_empty_task_type_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="task_type"):
            store.insert_observation(_observation(task_type=""))

    def test_whitespace_task_type_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="task_type"):
            store.insert_observation(_observation(task_type="   "))

    def test_empty_project_hash_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="project_hash"):
            store.insert_observation(_observation(project_hash=""))

    def test_empty_execution_mode_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="execution_mode"):
            store.insert_observation(_observation(execution_mode=""))

    def test_empty_review_mode_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="review_mode"):
            store.insert_observation(_observation(review_mode=""))

    def test_empty_verdict_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="verdict"):
            store.insert_observation(_observation(verdict=""))


# ---------------------------------------------------------------------------
# _validate_observation — negative numeric fields
# ---------------------------------------------------------------------------


class TestValidateObservationNegativeValues:
    def test_negative_actual_work_secs_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="actual_work_secs"):
            store.insert_observation(_observation(actual_work_secs=-1.0))

    def test_negative_actual_total_secs_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="actual_total_secs"):
            store.insert_observation(_observation(actual_total_secs=-0.5))

    def test_negative_error_ratio_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="error_ratio"):
            store.insert_observation(_observation(error_ratio=-0.1))

    def test_negative_review_overhead_secs_raises(self, store: SQLiteCalibrationStore) -> None:
        with pytest.raises(ValueError, match="review_overhead_secs"):
            store.insert_observation(_observation(review_overhead_secs=-5.0))

    def test_zero_values_accepted(self, store: SQLiteCalibrationStore) -> None:
        obs_id = store.insert_observation(
            _observation(
                actual_work_secs=0.0,
                actual_total_secs=0.0,
                error_ratio=0.0,
                review_overhead_secs=0.0,
            )
        )
        assert obs_id > 0


class TestTimestampNormalization:
    def test_equivalent_instants_share_utc_week_start(
        self,
        store: SQLiteCalibrationStore,
    ) -> None:
        store.insert_observation(
            _observation(observed_at="2026-03-01T22:30:00+00:00")
        )
        store.insert_observation(
            _observation(observed_at="2026-03-02T00:30:00+02:00")
        )

        rows = store._query_observations()

        assert {row["observed_at"] for row in rows} == {"2026-03-01T22:30:00+00:00"}
        assert {row["week_start"] for row in rows} == {"2026-02-23"}

    def test_observations_order_chronologically_after_utc_normalization(
        self,
        store: SQLiteCalibrationStore,
    ) -> None:
        later_id = store.insert_observation(
            _observation(observed_at="2026-03-02T20:00:00+00:00")
        )
        earlier_id = store.insert_observation(
            _observation(observed_at="2026-03-02T23:00:00+05:00")
        )

        rows = store._query_observations()

        assert [row["id"] for row in rows] == [earlier_id, later_id]
        assert [row["observed_at"] for row in rows] == [
            "2026-03-02T18:00:00+00:00",
            "2026-03-02T20:00:00+00:00",
        ]


# ---------------------------------------------------------------------------
# _percentile edge cases
# ---------------------------------------------------------------------------


class TestPercentileEdgeCases:
    def test_empty_list_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="percentile requires at least one value"):
            _percentile([], 50.0)

    def test_single_value_returns_that_value(self) -> None:
        assert _percentile([42.0], 50.0) == pytest.approx(42.0)

    def test_single_value_at_p0(self) -> None:
        assert _percentile([7.0], 0.0) == pytest.approx(7.0)

    def test_single_value_at_p100(self) -> None:
        assert _percentile([7.0], 100.0) == pytest.approx(7.0)

    def test_two_values_median(self) -> None:
        result = _percentile([10.0, 20.0], 50.0)
        assert result == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# Multiple task types in one calibrate cycle
# ---------------------------------------------------------------------------


class TestMultipleTaskTypesCalibrate:
    def test_multiple_task_types_produce_separate_summary_rows(
        self, store: SQLiteCalibrationStore
    ) -> None:
        for _ in range(5):
            store.insert_observation(_observation(task_type="feature", error_ratio=0.2))
        for _ in range(5):
            store.insert_observation(_observation(task_type="bugfix", error_ratio=0.3))

        store.calibrate()
        summaries = store.query_calibration_summary()

        task_types = {row["task_type"] for row in summaries}
        assert "feature" in task_types
        assert "bugfix" in task_types
        assert len(summaries) == 2

    def test_each_task_type_has_correct_count(
        self, store: SQLiteCalibrationStore
    ) -> None:
        for i in range(3):
            store.insert_observation(_observation(task_type="alpha", error_ratio=0.1 * (i + 1)))
        for i in range(7):
            store.insert_observation(_observation(task_type="beta", error_ratio=0.05 * (i + 1)))

        store.calibrate()
        summaries = {row["task_type"]: row for row in store.query_calibration_summary()}

        assert summaries["alpha"]["sample_count"] == 3
        assert summaries["beta"]["sample_count"] == 7

    def test_calibrate_holds_store_lock_for_full_recompute(
        self,
        store: SQLiteCalibrationStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        percentile_started = threading.Event()
        release_percentile = threading.Event()
        insert_finished = threading.Event()
        original_percentile = sqlite_store._percentile

        def blocking_percentile(values: list[float], percent: float) -> float:
            if percent == 50.0 and not percentile_started.is_set():
                percentile_started.set()
                release_percentile.wait(timeout=2)
            return original_percentile(values, percent)

        for i in range(3):
            store.insert_observation(_observation(task_type="alpha", error_ratio=0.1 * (i + 1)))

        monkeypatch.setattr(sqlite_store, "_percentile", blocking_percentile)

        calibrate_thread = threading.Thread(target=store.calibrate)
        calibrate_thread.start()
        assert percentile_started.wait(timeout=2)

        insert_thread = threading.Thread(
            target=lambda: (
                store.insert_observation(_observation(task_type="alpha", error_ratio=0.4)),
                insert_finished.set(),
            ),
        )
        insert_thread.start()

        assert insert_finished.wait(timeout=0.1) is False
        release_percentile.set()
        calibrate_thread.join(timeout=2)
        insert_thread.join(timeout=2)

        assert not calibrate_thread.is_alive()
        assert insert_finished.is_set()


# ---------------------------------------------------------------------------
# Custom k_anonymity_floor
# ---------------------------------------------------------------------------


class TestCustomKAnonymityFloor:
    def test_custom_floor_of_3_allows_smaller_cohorts(self, tmp_path: Path) -> None:
        store = SQLiteCalibrationStore(tmp_path / "k3.db", k_anonymity_floor=3)
        try:
            for i in range(3):
                store.insert_observation(_observation(task_type="small", error_ratio=0.1 * (i + 1)))
            store.calibrate()
            exported = store.export_calibration_summary(allow_export=True)
            assert len(exported) == 1
            assert exported[0]["task_type"] == "small"
        finally:
            store.close()

    def test_default_floor_of_5_excludes_small_cohorts(self, tmp_path: Path) -> None:
        store = SQLiteCalibrationStore(tmp_path / "k5.db")  # default k=5
        try:
            for i in range(4):  # 4 < 5
                store.insert_observation(_observation(task_type="tiny", error_ratio=0.1 * (i + 1)))
            store.calibrate()
            exported = store.export_calibration_summary(allow_export=True)
            # 4 records < floor=5, so excluded
            assert len(exported) == 0
        finally:
            store.close()
