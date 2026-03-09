"""Tests for internal vs external trace schema separation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_estimate.tracing.schema import (
    external_trace_json_schema,
    internal_trace_json_schema,
    validate_external_trace,
    validate_internal_trace,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _internal_trace(**overrides: object) -> dict:
    payload: dict = {
        "schema_version": "v1",
        "surface": "internal",
        "trace_id": "trace-int-001",
        "recorded_at": "2026-03-09T00:00:00Z",
        "producer": "agent-hub",
        "project": "agent-estimate",
        "environment": "prod",
        "event_type": "dispatch_lifecycle",
        "payload": {
            "dispatch_id": "dispatch-123",
            "dispatch_state": "in_progress",
            "actor": "codex",
            "task_ref": "hq#33/P2",
            "review_round": 1,
        },
    }
    payload.update(overrides)
    return payload


def _external_trace(**overrides: object) -> dict:
    payload: dict = {
        "schema_version": "v1",
        "surface": "external",
        "trace_id": "trace-ext-001",
        "recorded_at": "2026-03-09T00:00:00Z",
        "producer": "agent-estimate-api",
        "customer_id": "cust_123",
        "workspace_id": "ws_456",
        "environment": "prod",
        "event_type": "pipeline_stage",
        "payload": {
            "pipeline_run_id": "run_123",
            "stage": "estimate",
            "status": "running",
            "visible_label": "Estimating issue bundle",
            "duration_ms": 12,
        },
    }
    payload.update(overrides)
    return payload


class TestTraceValidation:
    def test_internal_trace_accepts_dispatch_lifecycle(self) -> None:
        trace = validate_internal_trace(_internal_trace())
        assert trace.surface == "internal"
        assert trace.payload.dispatch_id == "dispatch-123"

    def test_external_trace_accepts_pipeline_stage(self) -> None:
        trace = validate_external_trace(_external_trace())
        assert trace.surface == "external"
        assert trace.payload.stage == "estimate"

    def test_external_trace_rejects_internal_keys_in_extensions(self) -> None:
        with pytest.raises(ValidationError, match="internal-only fields"):
            validate_external_trace(
                _external_trace(
                    extensions={
                        "public_context": {
                            "conversation_id": "conv-001",
                        }
                    }
                )
            )

    def test_external_trace_rejects_internal_surface(self) -> None:
        with pytest.raises(ValidationError, match="surface"):
            validate_external_trace(_external_trace(surface="internal"))

    def test_internal_trace_rejects_external_event_type(self) -> None:
        with pytest.raises(ValidationError, match="event_type"):
            validate_internal_trace(_internal_trace(event_type="api_request"))


class TestSchemaArtifacts:
    def test_internal_schema_artifact_is_in_sync(self) -> None:
        schema_path = _repo_root() / "schemas" / "trace" / "internal_trace.schema.json"
        assert json.loads(schema_path.read_text(encoding="utf-8")) == internal_trace_json_schema()

    def test_external_schema_artifact_is_in_sync(self) -> None:
        schema_path = _repo_root() / "schemas" / "trace" / "external_trace.schema.json"
        assert json.loads(schema_path.read_text(encoding="utf-8")) == external_trace_json_schema()
