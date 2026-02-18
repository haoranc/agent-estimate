"""Tests for YAML config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_load_default_config_has_expected_profiles() -> None:
    config = load_default_config()

    assert [agent.name for agent in config.agents] == ["Claude", "Codex", "Gemini"]
