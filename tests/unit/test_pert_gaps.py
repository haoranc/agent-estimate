"""Additional PERT tests filling coverage gaps not in test_pert_engine.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_estimate.core.models import SizeTier, SizingResult, TaskType
from agent_estimate.core.modifiers import build_modifier_set
from agent_estimate.core.pert import (
    check_metr_threshold,
    estimate_task,
    load_metr_thresholds,
)
from agent_estimate.core.sizing import TIER_BASELINES


def _sizing(tier: SizeTier = SizeTier.S) -> SizingResult:
    o, m, p = TIER_BASELINES[tier]
    return SizingResult(
        tier=tier,
        baseline_optimistic=o,
        baseline_most_likely=m,
        baseline_pessimistic=p,
        task_type=TaskType.FEATURE,
        signals=(),
    )


# ---------------------------------------------------------------------------
# load_metr_thresholds — malformed YAML
# ---------------------------------------------------------------------------


class TestLoadMetrThresholdsMalformed:
    def test_malformed_yaml_raises_runtime_error(self, tmp_path: Path) -> None:
        malformed_yaml = "models:\n  opus: not_a_dict_with_p80\n"

        def fake_read_text(encoding: str) -> str:
            return malformed_yaml

        # Patch the resource path to return a tmp file we control
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("models:\n  opus:\n    no_p80_key: 10\n", encoding="utf-8")

        with patch(
            "agent_estimate.core.pert.files"
        ) as mock_files:
            mock_resource = mock_files.return_value.joinpath.return_value

            class FakePath:
                def read_text(self, encoding: str) -> str:
                    return "models:\n  opus:\n    no_p80_key: 10\n"

                def __enter__(self) -> "FakePath":
                    return self

                def __exit__(self, *_: object) -> None:
                    pass

            mock_resource.__enter__ = lambda s: FakePath()
            mock_resource.__exit__ = lambda s, *_: None

            from contextlib import contextmanager

            @contextmanager  # type: ignore[misc]
            def fake_as_file(resource: object):  # type: ignore[misc]
                yield FakePath()

            with patch("agent_estimate.core.pert.as_file", fake_as_file):
                with pytest.raises(RuntimeError, match="Malformed"):
                    load_metr_thresholds()

    def test_malformed_metr_yaml_via_file(self, tmp_path: Path) -> None:
        # Write a YAML that parses OK but has wrong structure (no p80_minutes key)
        bad_yaml = tmp_path / "metr_thresholds.yaml"
        bad_yaml.write_text(
            "models:\n  opus:\n    something_else: 10\n", encoding="utf-8"
        )

        from contextlib import contextmanager

        @contextmanager  # type: ignore[misc]
        def fake_as_file(resource: object):  # type: ignore[misc]
            yield bad_yaml

        with patch("agent_estimate.core.pert.as_file", fake_as_file):
            with pytest.raises(RuntimeError, match="Malformed"):
                load_metr_thresholds()


# ---------------------------------------------------------------------------
# estimate_task with explicit fallback_threshold
# ---------------------------------------------------------------------------


class TestEstimateTaskFallbackThreshold:
    def test_explicit_fallback_threshold_used_when_model_unknown(self) -> None:
        sizing = _sizing(SizeTier.M)
        mods = build_modifier_set()
        thresholds: dict[str, float] = {}  # empty — no known models

        # M tier expected ~50 min; fallback=10.0 → should warn
        result = estimate_task(
            sizing, mods, model_key="unknown", thresholds=thresholds, fallback_threshold=10.0
        )
        assert result.metr_warning is not None
        assert result.metr_warning.threshold_minutes == pytest.approx(10.0)

    def test_explicit_fallback_threshold_no_warn_when_below(self) -> None:
        sizing = _sizing(SizeTier.XS)
        mods = build_modifier_set()
        thresholds: dict[str, float] = {}

        # XS tier expected ~10 min; fallback=999.0 → no warn
        result = estimate_task(
            sizing, mods, model_key="new_model", thresholds=thresholds, fallback_threshold=999.0
        )
        assert result.metr_warning is None


# ---------------------------------------------------------------------------
# check_metr_threshold — thresholds=None triggers load
# ---------------------------------------------------------------------------


class TestCheckMetrThresholdAutoLoad:
    def test_none_thresholds_triggers_file_load(self) -> None:
        # Should not raise and should return a valid result using the real YAML
        result = check_metr_threshold("opus", 50.0, thresholds=None)
        # 50.0 is well within opus threshold of 90.0
        assert result is None

    def test_none_thresholds_warn_for_large_estimate(self) -> None:
        # A huge estimate should trigger warning via auto-load
        result = check_metr_threshold("opus", 99999.0, thresholds=None)
        assert result is not None
        assert result.model_key == "opus"
