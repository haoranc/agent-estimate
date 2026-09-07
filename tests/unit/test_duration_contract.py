"""Pin expected/cap separation through typed records, rendering and real CLI paths."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from agent_estimate.adapters.config_loader import _coerce_plugin_profile, load_default_config
from agent_estimate.adapters.sqlite_store import SQLiteCalibrationStore
from agent_estimate.cli.app import app
from agent_estimate.cli.commands._pipeline import run_estimate_pipeline
from agent_estimate.contract.duration import (
    forecast_from_report,
    resolve_scoring_basis,
    score_forecast,
)
from agent_estimate.contract.schema import (
    AdmissionEnvelope,
    CapCalculation,
    EstimateRequest,
    ForecastRecord,
)
from agent_estimate.core import EstimationConfig, ProjectSettings, ReviewMode
from agent_estimate.render import render_json_report, render_markdown_report

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
runner = CliRunner()


@pytest.fixture
def request_data():
    return yaml.safe_load((ROOT / "examples/estimate-request.yaml").read_text())


def calculation(**overrides):
    return CapCalculation(**{
        "base_field": "expected_minutes", "base_value": 70,
        "factors": [{"name": "rounds", "value": 2}, {"name": "headroom", "value": 1.5}],
        "rounding": "ceil", "rounding_increment": 5, "result": 210,
        **overrides,
    })


def record(request_data, **fields):
    return ForecastRecord(
        schema_version="agent-estimate/forecast/v1",
        request=EstimateRequest.model_validate(request_data), created_at_utc=NOW,
        engine={"version": "test", "registry_version": "test"}, **fields,
    )


def test_rounds_scale_only_the_cap_and_replay_survives_serialization(request_data):
    for rounds in (1, 2, 3):
        cap = calculation(factors=[{"name": "rounds", "value": rounds}], result=70 * rounds)
        request_data["admission"].update(
            declared_cap_minutes=cap.result, minutes_calculation=cap.model_dump(mode="json"),
        )
        forecast = record(request_data, expected_minutes=70, expected_review_minutes=15)
        assert forecast.expected_minutes == 70
        assert forecast.expected_review_minutes == 15
        assert score_forecast(forecast, 70) == 1
        restored = ForecastRecord.model_validate_json(forecast.model_dump_json())
        assert restored.request.admission.minutes_calculation.replay() == 70 * rounds
        assert [factor.name for factor in restored.request.admission.minutes_calculation.factors] == ["rounds"]


def test_rounding_occurs_only_after_ordered_factors():
    cap = calculation(base_value=1.01, factors=[
        {"name": "headroom", "value": 1.5}, {"name": "rounds", "value": 2},
    ], rounding_increment=1, result=4)
    assert cap.replay() == 4  # Rounding after each factor would produce 6.
    assert [factor.name for factor in cap.factors] == ["headroom", "rounds"]
    assert calculation(base_value=0.1, factors=[{"name": "headroom", "value": 3}],
                       rounding_increment=0.1, result=0.3).replay() == 0.3


@pytest.mark.parametrize("overrides", [
    {"result": 209}, {"rounding_increment": 0}, {"base_value": -1},
    {"factors": [{"name": "rounds", "value": True}]},
    {"factors": [{"name": "headroom", "value": float("nan")}]},
    {"factors": [{"name": "headroom", "value": float("inf")}]},
    {"factors": [{"name": "headroom", "value": -1}]},
    {"factors": [{"name": "headroom", "value": 0}]},
    {"base_value": 1e308, "factors": [{"name": "rounds", "value": 2}], "result": 1},
])
def test_invalid_cap_arithmetic_is_rejected(overrides):
    with pytest.raises(ValidationError):
        calculation(**overrides)


def test_file_axis_is_separate_and_replayable(request_data):
    files = calculation(base_field="expected_files_touched", base_value=13,
                        factors=[{"name": "headroom", "value": 1.5}],
                        rounding_increment=1, result=20)
    request_data["task_spec"]["scope"]["expected_files_touched"] = 13
    request_data["admission"].update(declared_cap_files_touched=20,
                                    files_calculation=files.model_dump(mode="json"))
    forecast = record(request_data, expected_minutes=70, expected_files_touched=13)
    assert forecast.expected_files_touched == 13
    assert forecast.request.admission.declared_cap_files_touched == 20
    assert forecast.request.admission.files_calculation.replay() == 20
    with pytest.raises(ValidationError, match="independent expected"):
        record(request_data, expected_minutes=70, expected_files_touched=20)
    with pytest.raises(ValidationError, match="axis"):
        AdmissionEnvelope(schema_version="agent-estimate/admission-envelope/v1",
                          declared_cap_minutes=20, minutes_calculation=files)


def test_cap_calculation_cannot_claim_another_expected_base(request_data):
    request_data["admission"].update(declared_cap_minutes=210,
                                    minutes_calculation=calculation().model_dump(mode="json"))
    with pytest.raises(ValidationError, match="independent expected"):
        record(request_data, expected_minutes=71)


def test_raw_cap_record_is_unscorable(request_data):
    with pytest.raises(ValueError, match="declared caps cannot be scored"):
        score_forecast(record(request_data), 30)
    with pytest.raises(ValidationError):
        record(request_data, expected_minutes=30, basis="declared-cap")


def test_expected_review_cannot_exceed_expected_wall(request_data):
    with pytest.raises(ValidationError, match="expected review cannot exceed expected wall"):
        record(request_data, expected_minutes=10, expected_review_minutes=15)


@pytest.mark.parametrize("review_mode,review_minutes", [
    (ReviewMode.STANDARD, 15), (ReviewMode.COMPLEX, 25), (ReviewMode.THREE_ROUND, 35),
])
def test_typed_report_forecast_uses_wall_and_additive_review(request_data, review_mode, review_minutes):
    cfg = load_default_config()
    cfg.agents = [cfg.agents[0]]
    report = run_estimate_pipeline(["Add validation"], cfg, review_mode=review_mode)
    request = EstimateRequest.model_validate(request_data)
    forecast = forecast_from_report(request, report, created_at_utc=NOW)
    assert forecast.expected_minutes == report.timeline.expected_case_minutes
    assert forecast.expected_minutes == pytest.approx(
        report.tasks[0].effective_duration_minutes * cfg.settings.friction_multiplier + review_minutes,
    )
    assert forecast.expected_review_minutes == review_minutes
    assert forecast.expected_files_touched is None  # File cap 3 is not an expectation.
    assert forecast.basis == "expected-wall"
    assert forecast.source == report.source
    assert forecast.as_of is None
    assert score_forecast(forecast, forecast.expected_minutes) == 1
    request_data["admission"]["declared_cap_minutes"] = 10000
    again = forecast_from_report(EstimateRequest.model_validate(request_data), report, created_at_utc=NOW)
    assert again.expected_minutes == forecast.expected_minutes


@pytest.mark.parametrize("factor", [0.5, 1.0, 2.0])
def test_actual_plugin_modifier_and_provenance_survive_rendering(factor):
    class Plugin:
        name = "Test"
        capabilities = ("implementation",)
        parallelism = 1
        cost_per_turn = 0
        model_tier = "unknown"
        # Configured multiplier deliberately disagrees with actual hook behavior.
        estimate_multiplier = 99

        def adjust_estimate(self, minutes):
            return minutes * factor

    cfg = EstimationConfig(agents=[_coerce_plugin_profile(Plugin(), "Test")],
                           settings=ProjectSettings(friction_multiplier=1, inter_wave_overhead=0, metr_fallback_threshold=45))
    report = run_estimate_pipeline(["Add validation"], cfg)
    task = report.tasks[0]
    assert task.estimate_factor == factor
    assert task.effective_duration_minutes == pytest.approx(task.work_before_adjustment_minutes * factor)
    markdown = render_markdown_report(report)
    payload = json.loads(render_json_report(report))
    assert payload["forecast"] == {
        "expected_minutes": report.timeline.expected_case_minutes,
        "basis": "expected-wall", "source": report.source, "as_of": None,
    }
    assert "Forecast basis: `expected-wall`" in markdown
    assert "as_of: unknown" in markdown
    if factor == 1:
        assert "Profile modifier (work minutes)" not in markdown
        assert "estimate_factor" not in payload["tasks"][0]["modifiers"]
    else:
        assert "Profile modifier (work minutes)" in markdown
        modifiers = payload["tasks"][0]["modifiers"]
        assert modifiers["estimate_factor"] == factor
        assert modifiers["pre_adjustment_minutes"] == task.work_before_adjustment_minutes
        assert modifiers["post_adjustment_minutes"] == task.effective_duration_minutes
        assert f"{factor:g}x:" in markdown


@pytest.mark.parametrize("fields", [
    {"declared_cap_minutes": 140},
    {"declared_cap_minutes": 140, "estimated_minutes": 140},
    {"estimated_minutes": 140, "basis": "declared-cap"},
    {"expected_minutes": 70, "basis": "cap-derived", "divisor": 2},
    {"admission": {"declared_cap_minutes": 140}},
])
def test_real_validation_path_rejects_caps_before_creating_db(tmp_path, fields):
    observation = tmp_path / "observation.yaml"
    observation.write_text(yaml.safe_dump({"actual_work_minutes": 60, **fields}))
    db = tmp_path / "calibration.db"
    result = runner.invoke(app, ["validate", str(observation), "--db", str(db)])
    assert result.exit_code == 2, result.output
    assert "caps cannot be scored" in result.output
    assert not db.exists()


def test_wall_scoring_uses_total_actual_and_refuses_legacy_work_storage(tmp_path):
    observation = tmp_path / "observation.yaml"
    observation.write_text(yaml.safe_dump({
        "expected_minutes": 40, "declared_cap_minutes": 140,
        "actual_work_minutes": 20, "actual_total_minutes": 40,
    }))
    result = runner.invoke(app, ["validate", str(observation)])
    assert result.exit_code == 0, result.output
    assert "Error ratio:       1.00" in result.output
    assert "expected-wall" in result.output
    db = tmp_path / "calibration.db"
    stored = runner.invoke(app, ["validate", str(observation), "--db", str(db)])
    assert stored.exit_code == 2
    assert "DB v1 accepts expected-work only" in stored.output
    assert not db.exists()


def test_legacy_history_is_excluded_until_its_basis_is_attested(tmp_path):
    db = tmp_path / "legacy.db"
    observation = tmp_path / "legacy.yaml"
    observation.write_text("estimated_minutes: 140\nactual_work_minutes: 70\n")
    inserted = runner.invoke(app, ["validate", str(observation), "--db", str(db)])
    assert inserted.exit_code == 0, inserted.output
    result = runner.invoke(app, ["calibrate", "--db", str(db)])
    assert result.exit_code == 2
    assert "Calibration excluded" in result.output
    with SQLiteCalibrationStore(db) as store:
        assert len(store._query_observations()) == 1
        assert store.query_calibration_summary() == []
    rejected = runner.invoke(app, ["calibrate", "--db", str(db), "--basis", "declared-cap"])
    assert rejected.exit_code == 2
    accepted = runner.invoke(app, ["calibrate", "--db", str(db), "--basis", "expected-work"])
    assert accepted.exit_code == 0
    assert "caller-attested legacy DB v1" in accepted.output
    with SQLiteCalibrationStore(db) as store:
        assert store.query_calibration_summary()[0]["sample_count"] == 1


def test_calibration_requires_basis_even_for_empty_database(tmp_path):
    db = tmp_path / "empty.db"
    with SQLiteCalibrationStore(db):
        pass
    missing = runner.invoke(app, ["calibrate", "--db", str(db)])
    assert missing.exit_code == 2
    assert "--basis expected-work" in missing.stderr
    assert missing.stdout == ""
    accepted = runner.invoke(app, ["calibrate", "--db", str(db), "--basis", "expected-work"])
    assert accepted.exit_code == 0
    assert "No calibration data available" in accepted.output


def test_legacy_alias_is_explicitly_work_only():
    assert resolve_scoring_basis({"estimated_minutes": 20}) == (20, "expected-work")
    with pytest.raises(ValueError, match="legacy estimated_minutes"):
        resolve_scoring_basis({"estimated_minutes": 20, "basis": "expected-wall"})
    with pytest.raises(ValueError, match="not both"):
        resolve_scoring_basis({"estimated_minutes": 20, "expected_minutes": 20})


@pytest.mark.parametrize("actual", [True, -1, float("nan"), float("inf"), 10**1000])
def test_scoring_rejects_invalid_actual_wall(request_data, actual):
    with pytest.raises((TypeError, ValueError), match="finite and non-negative"):
        score_forecast(record(request_data, expected_minutes=70), actual)
