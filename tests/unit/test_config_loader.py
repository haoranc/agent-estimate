"""Tests for YAML config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_estimate.adapters import config_loader
from agent_estimate.adapters.config_loader import load_config, load_default_config

VALID_CONFIG = """\
agents:
  - name: Claude
    capabilities:
      - planning
      - implementation
    parallelism: 2
    cost_per_turn: 0.12
    model_tier: frontier
settings:
  friction_multiplier: 1.1
  inter_wave_overhead: 0.25
  review_overhead: 0.15
  metr_fallback_threshold: 40.0
"""


@pytest.fixture(autouse=True)
def _disable_real_entry_point_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_loader, "_iter_agent_entry_points", lambda: [])


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_valid_file_returns_estimation_config(tmp_path: Path) -> None:
    config_path = _write(tmp_path, "config.yaml", VALID_CONFIG)

    config = load_config(config_path)

    assert config.settings.friction_multiplier == pytest.approx(1.1)
    assert len(config.agents) == 1
    assert config.agents[0].name == "Claude"
    assert config.agents[0].capabilities == ["planning", "implementation"]


def test_load_config_missing_required_field_has_clear_error(tmp_path: Path) -> None:
    missing_review = """\
agents:
  - name: Claude
    capabilities: [planning]
    parallelism: 2
    cost_per_turn: 0.12
    model_tier: frontier
settings:
  friction_multiplier: 1.1
  inter_wave_overhead: 0.25
  metr_fallback_threshold: 40.0
"""
    config_path = _write(tmp_path, "missing.yaml", missing_review)

    with pytest.raises(ValueError, match=r"settings\.review_overhead: Field required"):
        load_config(config_path)


def test_load_config_malformed_yaml_has_parse_error(tmp_path: Path) -> None:
    malformed = """\
agents:
  - name: Claude
    capabilities: [planning, implementation
"""
    config_path = _write(tmp_path, "malformed.yaml", malformed)

    with pytest.raises(ValueError, match="Failed to parse YAML config"):
        load_config(config_path)


def test_load_config_unknown_key_is_rejected(tmp_path: Path) -> None:
    with_unknown_key = """\
agents:
  - name: Claude
    capabilities: [planning]
    parallelism: 2
    cost_per_turn: 0.12
    model_tier: frontier
settings:
  friction_multiplier: 1.1
  inter_wave_overhead: 0.25
  review_overhead: 0.15
  metr_fallback_threshold: 40.0
  extra_setting: true
"""
    config_path = _write(tmp_path, "unknown-key.yaml", with_unknown_key)

    with pytest.raises(ValueError, match="settings.extra_setting: Extra inputs are not permitted"):
        load_config(config_path)


def test_load_config_accepts_yaml_int_values_for_float_fields(tmp_path: Path) -> None:
    int_values = """\
agents:
  - name: Claude
    capabilities: [planning]
    parallelism: 2
    cost_per_turn: 0
    model_tier: frontier
settings:
  friction_multiplier: 1
  inter_wave_overhead: 0
  review_overhead: 1
  metr_fallback_threshold: 30
"""
    config_path = _write(tmp_path, "int-values.yaml", int_values)

    config = load_config(config_path)

    assert config.agents[0].cost_per_turn == pytest.approx(0.0)
    assert config.settings.friction_multiplier == pytest.approx(1.0)
    assert config.settings.metr_fallback_threshold == pytest.approx(30.0)


def test_load_default_config_has_expected_profiles() -> None:
    config = load_default_config()

    assert [agent.name for agent in config.agents] == ["Claude", "Codex", "Gemini"]


def test_entry_point_group_is_stable() -> None:
    assert config_loader.ENTRY_POINT_GROUP == "agent_estimate.agents"


class _FakeEntryPoint:
    def __init__(self, name: str, loaded: object) -> None:
        self.name = name
        self._loaded = loaded

    def load(self) -> object:
        return self._loaded


class _CodexPluginProfile:
    name = "Codex"
    capabilities = ("implementation", "debugging", "testing", "profiling")
    parallelism = 5
    cost_per_turn = 0.2
    model_tier = "gpt-5.3"

    def adjust_estimate(self, minutes: float) -> float:
        return minutes * 0.95


def test_load_config_merges_plugin_profiles_with_plugin_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with_codex = """\
agents:
  - name: Codex
    capabilities: [implementation]
    parallelism: 1
    cost_per_turn: 0.08
    model_tier: production
settings:
  friction_multiplier: 1.1
  inter_wave_overhead: 0.25
  review_overhead: 0.15
  metr_fallback_threshold: 40.0
"""
    config_path = _write(tmp_path, "with-codex.yaml", with_codex)
    monkeypatch.setattr(
        config_loader,
        "_iter_agent_entry_points",
        lambda: [_FakeEntryPoint("codex_plugin", _CodexPluginProfile())],
    )

    config = load_config(config_path)

    assert len(config.agents) == 1
    assert config.agents[0].name == "Codex"
    assert config.agents[0].parallelism == 5
    assert config.agents[0].capabilities == [
        "implementation",
        "debugging",
        "testing",
        "profiling",
    ]
    assert config.agents[0].model_tier == "gpt-5.3"


def test_load_config_discovers_callable_entry_point_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _gemini_profile_factory() -> dict[str, object]:
        return {
            "name": "Gemini",
            "capabilities": ["research", "synthesis", "review"],
            "parallelism": 2,
            "cost_per_turn": 0.09,
            "model_tier": "gemini-3-pro",
        }

    config_path = _write(tmp_path, "config.yaml", VALID_CONFIG)
    monkeypatch.setattr(
        config_loader,
        "_iter_agent_entry_points",
        lambda: [_FakeEntryPoint("gemini_plugin", _gemini_profile_factory)],
    )

    config = load_config(config_path)

    assert [agent.name for agent in config.agents] == ["Claude", "Gemini"]
    assert config.agents[1].model_tier == "gemini-3-pro"
