"""Exercise the spec boundary without changing the legacy description contract."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import pytest
import typer
import yaml
from typer.testing import CliRunner

from agent_estimate.adapters.spec_loader import load_estimate_request
from agent_estimate.cli.app import app
from agent_estimate.cli.commands import estimate
from agent_estimate.contract import EstimateRequest

RUNNER = CliRunner()
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "estimate-request.yaml"


@pytest.fixture
def spec_data():
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _write_spec(tmp_path, data):
    path = tmp_path / "request.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _run(path, *options):
    return RUNNER.invoke(app, ["estimate", "--spec", str(path), *options])


def test_example_loads_typed_request_and_runs_in_both_formats():
    request = load_estimate_request(EXAMPLE)
    assert isinstance(request, EstimateRequest)
    assert request.task_spec.task_id == "example-task-1"
    assert request.admission.declared_cap_minutes == 90
    assert request.execution_profile.runtime.agent_name == "Codex"

    result = _run(EXAMPLE, "--format", "json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["schema_version"] == "agent-estimate/report/v1"
    assert report["tasks"][0]["name"] == "Add input validation"
    assert report["tasks"][0]["agent"] == "Codex"
    assert report["tasks"][0]["review_overhead_minutes"] == 15
    assert report["timeline"]["expected_case_minutes"] > 0
    result = _run(EXAMPLE, "--compact", "--title", "Spec example")
    assert result.exit_code == 0, result.output
    assert "# Spec example" in result.stdout
    assert "Schema: `agent-estimate/report/v1`" in result.stdout
    assert "## Wave Plan" not in result.stdout


def test_bare_description_requires_no_contract_fields(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("the bare path must not require a full request")

    monkeypatch.setattr(EstimateRequest, "model_validate", unexpected)
    result = RUNNER.invoke(app, ["estimate", "Fix typo", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert len(report["tasks"]) == 1
    assert "schema_version" not in report


@pytest.mark.parametrize(
    "path,value,field",
    [
        (("schema_version",), "v2", "schema_version"),
        (("task_spec", "description"), None, "task_spec.description"),
        (("task_spec", "scope", "estimated_tests"), True, "task_spec.scope.estimated_tests"),
        (("task_spec", "scope", "concerns"), -1, "task_spec.scope.concerns"),
        (("task_spec", "unexpected"), 1, "task_spec.unexpected"),
        (("execution_profile", "model"), {}, "execution_profile.model"),
        (
            ("execution_profile", "modifiers", "warm_context"),
            float("nan"), "execution_profile.modifiers.warm_context",
        ),
        (("admission", "declared_cap_minutes"), 0, "admission.declared_cap_minutes"),
    ],
)
def test_invalid_nested_fields_exit_two(tmp_path, spec_data, path, value, field):
    target = spec_data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2, result.output
    assert field in result.stderr
    assert not result.stdout


def test_missing_required_field_names_its_path(tmp_path, spec_data):
    del spec_data["task_spec"]["description"]
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2
    assert "task_spec.description" in result.stderr


@pytest.mark.parametrize("raw", ["", "null", "[]", "42", "a: [", "a: 1\na: 2", "? [a, b]\n: c"])
def test_invalid_yaml_documents_exit_two(tmp_path, raw):
    path = tmp_path / "invalid.yaml"
    path.write_text(raw, encoding="utf-8")
    result = _run(path)
    assert result.exit_code == 2, result.output
    assert "<root>" in result.stderr


def test_missing_directory_and_non_utf8_files_exit_two(tmp_path):
    invalid = tmp_path / "binary.yaml"
    invalid.write_bytes(b"\xff")
    for path in (tmp_path / "absent.yaml", tmp_path, invalid):
        result = _run(path)
        assert result.exit_code == 2, result.output
        assert "<root>" in result.stderr


@pytest.mark.parametrize(
    "options",
    [
        ["another task"], ["--file", "tasks.txt"], ["--issues", "1"],
        ["--review-mode", "standard"], ["--spec-clarity", "1.0"],
        ["--warm-context", "1.0"], ["--agent-fit", "1.0"], ["--auto-tier"],
        ["--no-auto-tier"], ["--estimated-tests", "3"], ["--estimated-lines", "30"],
        ["--num-concerns", "1"], ["--type", "coding"], ["--history-file", "data.json"],
        ["--history-agent", "Codex"], ["--history-project", "example"],
        ["--repo", "owner/repo"],
    ],
)
def test_spec_conflicts_rejected_before_input_or_network(monkeypatch, options):
    def unexpected(*args, **kwargs):
        raise AssertionError("conflicting input must be rejected before loading")

    monkeypatch.setattr(estimate, "load_estimate_request", unexpected)
    monkeypatch.setattr(estimate, "_fetch_github_task_descriptions", unexpected)
    result = _run(EXAMPLE, *options)
    assert result.exit_code == 2, result.output
    assert "only one input source" in result.stderr or "cannot be combined" in result.stderr


def test_parameter_source_does_not_depend_on_click_enum_identity(monkeypatch):
    # Newer Typer vendors its CLI internals; its enum is a different class.
    source_type = Enum("IndependentSource", "COMMANDLINE DEFAULT")
    original = typer.Context.get_parameter_source

    def independent_source(self, name):
        source = original(self, name)
        if source is not None and source.name in source_type.__members__:
            return source_type[source.name]
        return source

    monkeypatch.setattr(typer.Context, "get_parameter_source", independent_source)
    result = _run(EXAMPLE, "--spec-clarity", "1.0")
    assert result.exit_code == 2
    assert "--spec-clarity" in result.stderr


def test_spec_modifiers_and_scope_override_engine_defaults(tmp_path, spec_data):
    spec_data["task_spec"]["task_type"] = "documentation"
    spec_data["task_spec"]["scope"]["estimated_tests"] = 100
    spec_data["execution_profile"]["modifiers"] = {
        "spec_clarity": 0.7, "warm_context": 0.5, "agent_fit": 1.1,
    }
    spec_data["execution_profile"]["review"] = {
        "mode": "none", "expected_rounds": 0, "intensity": "standard",
    }
    result = _run(_write_spec(tmp_path, spec_data), "--format", "json")
    assert result.exit_code == 0, result.output
    task = json.loads(result.stdout)["tasks"][0]
    assert task["estimation_category"] == "documentation"
    assert task["review_overhead_minutes"] == 0
    assert task["modifiers"]["spec_clarity"] == 0.7
    assert task["modifiers"]["warm_context"] == 0.5
    assert task["modifiers"]["agent_fit"] == 1.1
    assert task["tier_correction_warnings"]


def test_spec_uses_no_ambient_history_and_never_treats_caps_as_forecasts(
    tmp_path, spec_data, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    spec_data["execution_profile"]["modifiers"].pop("warm_context")
    path = _write_spec(tmp_path, spec_data)
    baseline = _run(path, "--format", "json")
    assert baseline.exit_code == 0
    (tmp_path / "data.json").write_text("not dispatch history", encoding="utf-8")
    spec_data["admission"]["declared_cap_minutes"] = 5000
    spec_data["admission"]["declared_cap_files_touched"] = 200
    result = _run(_write_spec(tmp_path, spec_data), "--format", "json")
    assert result.exit_code == 0
    assert result.stdout == baseline.stdout
    assert result.stderr == baseline.stderr
    assert json.loads(result.stdout)["tasks"][0]["modifiers"]["warm_context"] == 1.0


def test_implicit_context_is_applied_once_and_explicit_context_conflict_rejected(
    tmp_path, spec_data,
):
    profile = spec_data["execution_profile"]
    profile["modifiers"].pop("warm_context")
    profile["execution_mode"] = "co_dispatch"
    profile["context"] = {"state": "task_warm", "context_key": "example", "implicit_co_dispatch": True}
    result = _run(_write_spec(tmp_path, spec_data), "--format", "json")
    assert result.exit_code == 0, result.output
    task = json.loads(result.stdout)["tasks"][0]
    assert task["modifiers"]["combined"] == 0.5
    profile["modifiers"]["warm_context"] = 0.5
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2
    assert "execution_profile" in result.stderr
    assert "double counting" in result.stderr


def test_unknown_agent_and_unsupported_review_plan_are_explicit_errors(tmp_path, spec_data):
    spec_data["execution_profile"]["runtime"]["agent_name"] = "not-configured"
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2
    assert "execution_profile.runtime.agent_name" in result.stderr
    spec_data["execution_profile"]["runtime"]["agent_name"] = "Codex"
    spec_data["execution_profile"]["review"] = {
        "mode": "review_loop", "expected_rounds": 4, "intensity": "complex",
    }
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2
    assert "execution_profile.review" in result.stderr


@pytest.mark.parametrize(
    "owner,field,value",
    [
        ("task_spec", "dependency_task_ids", ["another-task"]),
        ("execution_profile", "estimate_multiplier", 2.0),
    ],
)
def test_unsupported_execution_facts_cannot_be_silently_ignored(
    tmp_path, spec_data, owner, field, value,
):
    spec_data[owner][field] = value
    result = _run(_write_spec(tmp_path, spec_data))
    assert result.exit_code == 2
    assert f"{owner}.{field}" in result.stderr


def _write_config(tmp_path, *, factor=1.0, removed_key=False):
    agents = [
        {"name": "Codex", "capabilities": ["implementation", "testing"], "parallelism": 1,
         "cost_per_turn": 1, "model_tier": "production", "estimate_multiplier": factor},
        {"name": "Other", "capabilities": ["review"], "parallelism": 1,
         "cost_per_turn": 1, "model_tier": "production"},
    ]
    settings = {"friction_multiplier": 1.3, "inter_wave_overhead": 0, "metr_fallback_threshold": 45}
    if removed_key:
        settings["review_overhead"] = None
    path = tmp_path / "agents.yaml"
    path.write_text(yaml.safe_dump({"agents": agents, "settings": settings}))
    return path


def test_spec_capabilities_are_enforced_without_fallback(tmp_path, spec_data):
    config = _write_config(tmp_path)
    spec_data["task_spec"]["required_capabilities"] = ["implementation", "testing"]
    result = _run(_write_spec(tmp_path, spec_data), "--config", str(config), "--format", "json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["tasks"][0]["agent"] == "Codex"
    spec_data["task_spec"]["required_capabilities"] = ["review"]
    result = _run(_write_spec(tmp_path, spec_data), "--config", str(config))
    assert result.exit_code == 2
    assert "No eligible agent" in result.stderr
    assert "review" in result.stderr
    assert result.stdout == ""


def test_config_multiplier_changes_work_once_and_keeps_review_and_human_work(tmp_path, spec_data):
    path = _write_spec(tmp_path, spec_data)
    config = _write_config(tmp_path)
    baseline = _run(path, "--config", str(config), "--format", "json")
    assert baseline.exit_code == 0, baseline.output
    before = json.loads(baseline.stdout)
    _write_config(tmp_path, factor=2.0)
    result = _run(path, "--config", str(config), "--format", "json")
    assert result.exit_code == 0, result.output
    after = json.loads(result.stdout)
    assert after["tasks"][0]["effective_duration_minutes"] == pytest.approx(
        2 * before["tasks"][0]["effective_duration_minutes"],
    )
    assert after["timeline"]["expected_case_minutes"] == pytest.approx(
        2 * (before["timeline"]["expected_case_minutes"] - 15) + 15,
    )
    assert after["agent_load"][0]["heuristic_cost"] == pytest.approx(
        2 * before["agent_load"][0]["heuristic_cost"],
    )
    assert after["timeline"]["human_equivalent_minutes"] == before["timeline"]["human_equivalent_minutes"]
    assert after["tasks"][0]["review_overhead_minutes"] == 15
    assert "estimated_cost" not in after["agent_load"][0]


@pytest.mark.parametrize("use_spec", [False, True])
def test_removed_config_key_exits_two_with_migration_guidance(tmp_path, spec_data, use_spec):
    config = _write_config(tmp_path, removed_key=True)
    options = ["--config", str(config)]
    if use_spec:
        result = _run(_write_spec(tmp_path, spec_data), *options)
    else:
        result = RUNNER.invoke(app, ["estimate", "Fix typo", *options])
    assert result.exit_code == 2
    assert "settings.review_overhead was removed; delete this key" in result.stderr
    assert "--review-mode" in result.stderr
    assert result.stdout == ""
