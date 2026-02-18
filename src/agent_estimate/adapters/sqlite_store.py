"""SQLite persistence adapter for calibration history."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class ObservationInput:
    """Input payload for one calibration observation."""

    task_type: str
    estimated_secs: float
    actual_work_secs: float
    actual_total_secs: float
    error_ratio: float
    file_count: int
    line_count: int
    test_count: int
    project_hash: str
    spec_clarity_modifier: float
    warm_context_modifier: float
    execution_mode: str
    review_mode: str
    review_overhead_secs: float
    verdict: str
    modifiers_should_have_been: dict[str, float]
    observed_at: str | None = None


class SQLiteCalibrationStore:
    """SQLite-backed storage and aggregation for calibration metrics."""

    def __init__(
        self,
        path: str | Path,
        *,
        k_anonymity_floor: int = 5,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._k_anonymity_floor = k_anonymity_floor
        self._lock = RLock()
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._enable_pragmas()
        self._create_schema()

    def __enter__(self) -> SQLiteCalibrationStore:
        """Allow `with SQLiteCalibrationStore(...) as store:` usage."""
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the backing SQLite connection."""
        with self._lock:
            self._connection.close()

    def journal_mode(self) -> str:
        """Return the active SQLite journal mode."""
        with self._lock:
            row = self._connection.execute("PRAGMA journal_mode").fetchone()
        if row is None:
            return ""
        return str(row[0]).lower()

    def insert_observation(self, observation: ObservationInput) -> int:
        """Insert one observation row and return its id."""
        _validate_observation(observation)
        task_type_id = self._upsert_task_type(observation.task_type.strip())
        observed_at = _normalize_timestamp(observation.observed_at)
        week_start = _week_start(observed_at)
        encoded_modifiers = json.dumps(observation.modifiers_should_have_been, sort_keys=True)

        with self._lock:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    INSERT INTO observations (
                      task_type_id,
                      observed_at,
                      week_start,
                      estimated_secs,
                      actual_work_secs,
                      actual_total_secs,
                      error_ratio,
                      file_count,
                      line_count,
                      test_count,
                      project_hash,
                      spec_clarity_modifier,
                      warm_context_modifier,
                      execution_mode,
                      review_mode,
                      review_overhead_secs,
                      verdict,
                      modifiers_should_have_been
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_type_id,
                        observed_at,
                        week_start,
                        observation.estimated_secs,
                        observation.actual_work_secs,
                        observation.actual_total_secs,
                        observation.error_ratio,
                        observation.file_count,
                        observation.line_count,
                        observation.test_count,
                        observation.project_hash,
                        observation.spec_clarity_modifier,
                        observation.warm_context_modifier,
                        observation.execution_mode,
                        observation.review_mode,
                        observation.review_overhead_secs,
                        observation.verdict,
                        encoded_modifiers,
                    ),
                )
        return int(cursor.lastrowid)

    def _query_observations(
        self,
        *,
        task_type: str | None = None,
        week_start: str | None = None,
    ) -> list[dict[str, Any]]:
        """Internal raw-row query helper for local diagnostics/testing only."""
        clauses: list[str] = []
        params: list[Any] = []

        if task_type is not None:
            clauses.append("task_types.name = ?")
            params.append(task_type)
        if week_start is not None:
            clauses.append("observations.week_start = ?")
            params.append(week_start)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT
                  observations.id,
                  task_types.name AS task_type,
                  observations.observed_at,
                  observations.week_start,
                  observations.estimated_secs,
                  observations.actual_work_secs,
                  observations.actual_total_secs,
                  observations.error_ratio,
                  observations.file_count,
                  observations.line_count,
                  observations.test_count,
                  observations.project_hash,
                  observations.spec_clarity_modifier,
                  observations.warm_context_modifier,
                  observations.execution_mode,
                  observations.review_mode,
                  observations.review_overhead_secs,
                  observations.verdict,
                  observations.modifiers_should_have_been
                FROM observations
                INNER JOIN task_types ON task_types.id = observations.task_type_id
                {where_sql}
                ORDER BY observations.observed_at ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def calibrate(self) -> None:
        """Recompute calibration_summary from the raw observations table."""
        grouped: dict[tuple[str, int], list[float]] = {}
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT week_start, task_type_id, error_ratio
                FROM observations
                ORDER BY week_start ASC, task_type_id ASC
                """,
            ).fetchall()

        for row in rows:
            key = (str(row["week_start"]), int(row["task_type_id"]))
            grouped.setdefault(key, []).append(float(row["error_ratio"]) * 100.0)

        with self._lock:
            with self._connection:
                self._connection.execute("DELETE FROM calibration_summary")
                for (week_start, task_type_id), values in grouped.items():
                    median_error_pct = _percentile(values, 50.0)
                    p10 = _percentile(values, 10.0)
                    p90 = _percentile(values, 90.0)
                    self._connection.execute(
                        """
                        INSERT INTO calibration_summary (
                          week_start,
                          task_type_id,
                          median_error_pct,
                          p10,
                          p90,
                          sample_count
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            week_start,
                            task_type_id,
                            median_error_pct,
                            p10,
                            p90,
                            len(values),
                        ),
                    )

    def query_calibration_summary(self) -> list[dict[str, Any]]:
        """Return all aggregate rows from calibration_summary."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                  calibration_summary.week_start,
                  task_types.name AS task_type,
                  calibration_summary.median_error_pct,
                  calibration_summary.p10,
                  calibration_summary.p90,
                  calibration_summary.sample_count
                FROM calibration_summary
                INNER JOIN task_types ON task_types.id = calibration_summary.task_type_id
                ORDER BY calibration_summary.week_start ASC, task_types.name ASC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def export_calibration_summary(self, *, allow_export: bool = False) -> list[dict[str, Any]]:
        """Export only aggregate data, gated by explicit allow_export."""
        if not allow_export:
            raise PermissionError("Export is disabled by default. Pass allow_export=True to export.")

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT
                  calibration_summary.week_start,
                  task_types.name AS task_type,
                  calibration_summary.median_error_pct,
                  calibration_summary.p10,
                  calibration_summary.p90,
                  calibration_summary.sample_count
                FROM calibration_summary
                INNER JOIN task_types ON task_types.id = calibration_summary.task_type_id
                WHERE calibration_summary.sample_count >= ?
                ORDER BY calibration_summary.week_start ASC, task_types.name ASC
                """,
                (self._k_anonymity_floor,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _enable_pragmas(self) -> None:
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=5000")

    def _create_schema(self) -> None:
        with self._lock:
            with self._connection:
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_types (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL UNIQUE
                    )
                    """,
                )
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS observations (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      task_type_id INTEGER NOT NULL,
                      observed_at TEXT NOT NULL,
                      week_start TEXT NOT NULL,
                      estimated_secs REAL NOT NULL,
                      actual_work_secs REAL NOT NULL,
                      actual_total_secs REAL NOT NULL,
                      error_ratio REAL NOT NULL,
                      file_count INTEGER NOT NULL,
                      line_count INTEGER NOT NULL,
                      test_count INTEGER NOT NULL,
                      project_hash TEXT NOT NULL,
                      spec_clarity_modifier REAL NOT NULL,
                      warm_context_modifier REAL NOT NULL,
                      execution_mode TEXT NOT NULL,
                      review_mode TEXT NOT NULL,
                      review_overhead_secs REAL NOT NULL,
                      verdict TEXT NOT NULL,
                      modifiers_should_have_been TEXT NOT NULL,
                      FOREIGN KEY (task_type_id) REFERENCES task_types(id)
                    )
                    """,
                )
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS calibration_summary (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      week_start TEXT NOT NULL,
                      task_type_id INTEGER NOT NULL,
                      median_error_pct REAL NOT NULL,
                      p10 REAL NOT NULL,
                      p90 REAL NOT NULL,
                      sample_count INTEGER NOT NULL,
                      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      UNIQUE (week_start, task_type_id),
                      FOREIGN KEY (task_type_id) REFERENCES task_types(id)
                    )
                    """,
                )
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_version (
                      version INTEGER PRIMARY KEY,
                      applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                )
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO schema_version (version) VALUES (1)
                    """,
                )

    def _upsert_task_type(self, task_type: str) -> int:
        if not task_type:
            raise ValueError("task_type must be non-empty")

        with self._lock:
            with self._connection:
                self._connection.execute(
                    "INSERT OR IGNORE INTO task_types (name) VALUES (?)",
                    (task_type,),
                )
            row = self._connection.execute(
                "SELECT id FROM task_types WHERE name = ?",
                (task_type,),
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve task type id for '{task_type}'")
        return int(row["id"])


def calibrate(path: str | Path) -> list[dict[str, Any]]:
    """Convenience wrapper: open store, recompute summaries, and close store."""
    store = SQLiteCalibrationStore(path)
    try:
        store.calibrate()
        return store.query_calibration_summary()
    finally:
        store.close()


def _validate_observation(observation: ObservationInput) -> None:
    if not observation.task_type.strip():
        raise ValueError("task_type must be non-empty")
    if not observation.project_hash.strip():
        raise ValueError("project_hash must be non-empty")
    if not observation.execution_mode.strip():
        raise ValueError("execution_mode must be non-empty")
    if not observation.review_mode.strip():
        raise ValueError("review_mode must be non-empty")
    if not observation.verdict.strip():
        raise ValueError("verdict must be non-empty")

    for name, value in (
        ("estimated_secs", observation.estimated_secs),
        ("actual_work_secs", observation.actual_work_secs),
        ("actual_total_secs", observation.actual_total_secs),
        ("error_ratio", observation.error_ratio),
        ("review_overhead_secs", observation.review_overhead_secs),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0")

    for name, value in (
        ("file_count", observation.file_count),
        ("line_count", observation.line_count),
        ("test_count", observation.test_count),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0")

    for key, value in observation.modifiers_should_have_been.items():
        if not str(key).strip():
            raise ValueError("modifiers_should_have_been keys must be non-empty")
        if not isinstance(value, (int, float)):
            raise ValueError("modifiers_should_have_been values must be numeric")


def _normalize_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    return value


def _week_start(timestamp: str) -> str:
    normalized = timestamp.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    monday = (dt - timedelta(days=dt.weekday())).date()
    return monday.isoformat()


def _percentile(values: list[float], percent: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if len(values) == 1:
        return values[0]

    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (percent / 100.0)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)

    if lower_index == upper_index:
        return sorted_values[lower_index]

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    fraction = rank - lower_index
    return lower_value + (upper_value - lower_value) * fraction
