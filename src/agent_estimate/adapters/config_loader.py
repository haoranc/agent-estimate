"""YAML-backed configuration loader with plugin-aware profile discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib.metadata import EntryPoint, entry_points
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agent_estimate.core.models import (
    AgentProfile,
    AgentProfileProtocol,
    EstimationConfig,
)

DEFAULT_CONFIG_FILENAME = "default_agents.yaml"
ENTRY_POINT_GROUP = "agent_estimate.agents"


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
        config = EstimationConfig.model_validate(raw_data)
    except ValidationError as exc:
        detail_text = _format_validation_errors(exc)
        raise ValueError(f"Invalid config file at {config_path}:\n{detail_text}") from exc

    merged_agents = discover_agent_profiles(config.agents)
    return config.model_copy(update={"agents": merged_agents})


def load_default_config() -> EstimationConfig:
    """Load the packaged default agent configuration."""
    resource = files("agent_estimate").joinpath(DEFAULT_CONFIG_FILENAME)
    with as_file(resource) as default_path:
        return load_config(default_path)


def discover_agent_profiles(base_profiles: Sequence[AgentProfile]) -> list[AgentProfile]:
    """Merge YAML profiles with installed entry-point plugins.

    Profiles discovered from entry points take precedence over same-name YAML
    profiles. YAML remains the fallback for names not provided by plugins.
    """
    merged = {profile.name: profile for profile in base_profiles}
    for plugin_profile in discover_plugin_profiles():
        merged[plugin_profile.name] = plugin_profile
    return list(merged.values())


def discover_plugin_profiles() -> list[AgentProfile]:
    """Discover and validate agent profiles from entry points."""
    discovered: dict[str, AgentProfile] = {}
    for ep in _iter_agent_entry_points():
        profile = _load_entry_point_profile(ep)
        discovered[profile.name] = profile
    return list(discovered.values())


def _iter_agent_entry_points() -> list[EntryPoint]:
    all_entry_points = entry_points()
    if hasattr(all_entry_points, "select"):
        return list(all_entry_points.select(group=ENTRY_POINT_GROUP))
    if isinstance(all_entry_points, Mapping):
        return list(all_entry_points.get(ENTRY_POINT_GROUP, ()))
    return [ep for ep in all_entry_points if getattr(ep, "group", None) == ENTRY_POINT_GROUP]


def _load_entry_point_profile(ep: EntryPoint) -> AgentProfile:
    try:
        loaded = ep.load()
    except Exception as exc:  # pragma: no cover - defensive path
        raise ValueError(f"Failed to load entry point {ep.name!r}: {exc}") from exc
    return _coerce_plugin_profile(loaded, ep.name)


def _coerce_plugin_profile(raw: object, entry_point_name: str) -> AgentProfile:
    candidate = raw

    if (
        callable(candidate)
        and not isinstance(candidate, AgentProfile)
        and not isinstance(candidate, Mapping)
        and not isinstance(candidate, AgentProfileProtocol)
    ):
        try:
            candidate = candidate()
        except Exception as exc:
            raise ValueError(
                f"Entry point {entry_point_name!r} callable failed: {exc}"
            ) from exc

    if isinstance(candidate, AgentProfile):
        return candidate

    payload: dict[str, Any]
    if isinstance(candidate, AgentProfileProtocol):
        payload = {
            "name": candidate.name,
            "capabilities": list(candidate.capabilities),
            "parallelism": candidate.parallelism,
            "cost_per_turn": candidate.cost_per_turn,
            "model_tier": candidate.model_tier,
        }
    elif isinstance(candidate, Mapping):
        payload = dict(candidate)
    else:
        raise ValueError(
            "Entry point "
            f"{entry_point_name!r} must resolve to an AgentProfile, mapping, "
            "AgentProfileProtocol instance, or zero-arg callable that returns one."
        )

    try:
        return AgentProfile.model_validate(payload)
    except ValidationError as exc:
        detail_text = _format_validation_errors(exc)
        raise ValueError(
            f"Invalid profile from entry point {entry_point_name!r}:\n{detail_text}"
        ) from exc


def _format_validation_errors(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
        details.append(f"{location}: {error['msg']}")
    return "\n".join(f"- {line}" for line in details)
