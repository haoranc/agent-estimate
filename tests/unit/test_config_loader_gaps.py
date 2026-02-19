"""Additional config_loader tests filling coverage gaps."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_estimate.adapters.config_loader import load_config


def _write(tmp_path: Path, filename: str, content: str) -> Path:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Non-existent path
# ---------------------------------------------------------------------------


class TestLoadConfigNonExistentPath:
    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# Empty YAML
# ---------------------------------------------------------------------------


class TestLoadConfigEmptyYaml:
    def test_empty_file_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "empty.yaml", "")
        # Empty YAML → raw_data is None → treated as {} → fails EstimationConfig validation
        with pytest.raises(ValueError):
            load_config(path)

    def test_yaml_with_only_comments_raises(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "comments.yaml", "# just a comment\n")
        with pytest.raises(ValueError):
            load_config(path)


# ---------------------------------------------------------------------------
# YAML root is a list, not a dict
# ---------------------------------------------------------------------------


class TestLoadConfigYamlRootList:
    def test_root_list_raises_value_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "list.yaml", "- item1\n- item2\n")
        with pytest.raises(ValueError, match="root must be a YAML mapping"):
            load_config(path)

    def test_root_string_raises_value_error(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "string.yaml", "just a string\n")
        with pytest.raises(ValueError, match="root must be a YAML mapping"):
            load_config(path)
