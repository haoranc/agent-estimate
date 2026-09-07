"""Load a YAML file through the versioned estimate-request boundary."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_estimate.contract import EstimateRequest


class _UniqueKeyLoader(yaml.SafeLoader):
    """Reject ambiguous mappings instead of silently taking the last value."""

    def construct_mapping(self, node, deep=False):
        self.flatten_mapping(node)
        keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in keys
                keys.add(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    None, None, "mapping keys must be scalar", key_node.start_mark
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
        return super().construct_mapping(node, deep=deep)


def load_estimate_request(path: Path) -> EstimateRequest:
    """Read one full contract document; validation errors name dotted fields."""
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: <root>: {exc}") from exc
    try:
        return EstimateRequest.model_validate(raw)
    except ValidationError as exc:
        details = "\n".join(
            f"- {'.'.join(map(str, error['loc'])) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"{path}:\n{details}") from exc
