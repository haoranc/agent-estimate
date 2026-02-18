"""YAML-backed configuration loader with Pydantic validation."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_estimate.core.models import EstimationConfig

DEFAULT_CONFIG_FILENAME = "default_agents.yaml"


def load_config(path: str | Path) -> EstimationConfig:
    """Load and validate an estimation configuration file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        raw_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML config at {config_path}: {exc}") from exc
    except OSError as exc:
        raise OSError(f"Failed to read config file {config_path}: {exc}") from exc

    if raw_data is None:
        raw_data = {}
    if not isinstance(raw_data, dict):
        raise ValueError(f"Invalid config file at {config_path}: root must be a YAML mapping")

    try:
        return EstimationConfig.model_validate(raw_data)
    except ValidationError as exc:
        details: list[str] = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
            details.append(f"{location}: {error['msg']}")
        detail_text = "\n".join(f"- {line}" for line in details)
        raise ValueError(f"Invalid config file at {config_path}:\n{detail_text}") from exc


def load_default_config() -> EstimationConfig:
    """Load the packaged default agent configuration."""
    resource = files("agent_estimate").joinpath(DEFAULT_CONFIG_FILENAME)
    with as_file(resource) as default_path:
        return load_config(default_path)
