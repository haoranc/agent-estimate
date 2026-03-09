"""Strict trace schemas for internal operations vs external customer surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, TypeAdapter
from pydantic import model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ExtensionKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z][a-z0-9_.-]*$"),
]

MessageType = Literal[
    "task_request",
    "question",
    "notification",
    "follow_up",
    "handoff",
    "handoff_complete",
    "review_request",
    "review_feedback",
    "review_addressed",
    "review_lgtm",
    "brainstorm_request",
    "brainstorm_followup",
]

DispatchState = Literal[
    "queued",
    "in_progress",
    "blocked",
    "awaiting_review",
    "completed",
    "cancelled",
]

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
PipelineStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

TraceExtensions: TypeAlias = dict[ExtensionKey, JsonValue]

_INTERNAL_ONLY_KEYS = frozenset(
    {
        "agent",
        "context_keys",
        "conversation_id",
        "dispatch_id",
        "dispatch_state",
        "inbox_path",
        "message_id",
        "message_type",
        "outbox_path",
        "parent_message_id",
        "peer_agent",
        "review_round",
        "task_ref",
    }
)
_INTERNAL_ONLY_PREFIXES = (
    "agent_",
    "conversation_",
    "dispatch_",
    "inbox_",
    "outbox_",
    "parent_message_",
    "review_",
)


def _find_internal_key_path(value: JsonValue, path: tuple[str, ...] = ()) -> str | None:
    """Return the first nested path that uses a reserved internal key."""
    if isinstance(value, Mapping):
        for key, nested in value.items():
            current_path = (*path, key)
            if key in _INTERNAL_ONLY_KEYS or key.startswith(_INTERNAL_ONLY_PREFIXES):
                return ".".join(current_path)
            nested_path = _find_internal_key_path(nested, current_path)
            if nested_path:
                return nested_path
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            nested_path = _find_internal_key_path(item, (*path, str(index)))
            if nested_path:
                return nested_path
    return None


class SchemaModel(BaseModel):
    """Base class for strict trace payloads."""

    model_config = ConfigDict(extra="forbid")


class InternalTraceBase(SchemaModel):
    """Common envelope for internal operational traces."""

    schema_version: Literal["v1"] = "v1"
    surface: Literal["internal"] = "internal"
    trace_id: NonEmptyStr
    recorded_at: datetime
    producer: NonEmptyStr
    project: NonEmptyStr
    environment: Literal["dev", "staging", "prod"]
    extensions: TraceExtensions = Field(default_factory=dict)


class AgentCoordinationPayload(SchemaModel):
    """Coordination traces between agents or orchestrators."""

    coordination_id: NonEmptyStr
    agent: NonEmptyStr
    peer_agent: NonEmptyStr | None = None
    action: Literal[
        "task_request",
        "notification",
        "question",
        "handoff",
        "review_request",
        "review_feedback",
        "review_lgtm",
        "status_update",
    ]
    conversation_id: NonEmptyStr | None = None
    context_keys: list[NonEmptyStr] = Field(default_factory=list)


class AgentCoordinationTrace(InternalTraceBase):
    """Internal trace for agent coordination events."""

    event_type: Literal["agent_coordination"] = "agent_coordination"
    payload: AgentCoordinationPayload


class InboxProtocolPayload(SchemaModel):
    """Inbox / outbox protocol event details."""

    message_id: NonEmptyStr
    message_type: MessageType
    sender: NonEmptyStr
    recipient: NonEmptyStr
    inbox_path: NonEmptyStr
    outbox_path: NonEmptyStr | None = None
    parent_message_id: NonEmptyStr | None = None


class InboxProtocolTrace(InternalTraceBase):
    """Internal trace for message protocol lifecycle events."""

    event_type: Literal["inbox_protocol"] = "inbox_protocol"
    payload: InboxProtocolPayload


class DispatchLifecyclePayload(SchemaModel):
    """Dispatch state transition details."""

    dispatch_id: NonEmptyStr
    dispatch_state: DispatchState
    actor: NonEmptyStr
    task_ref: NonEmptyStr
    review_round: Annotated[int, Field(ge=0)] | None = None


class DispatchLifecycleTrace(InternalTraceBase):
    """Internal trace for dispatch lifecycle transitions."""

    event_type: Literal["dispatch_lifecycle"] = "dispatch_lifecycle"
    payload: DispatchLifecyclePayload


class ExternalTraceBase(SchemaModel):
    """Common envelope for customer-visible trace events."""

    schema_version: Literal["v1"] = "v1"
    surface: Literal["external"] = "external"
    trace_id: NonEmptyStr
    recorded_at: datetime
    producer: NonEmptyStr
    customer_id: NonEmptyStr
    workspace_id: NonEmptyStr
    environment: Literal["dev", "staging", "prod"]
    extensions: TraceExtensions = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_internal_fields(self) -> "ExternalTraceBase":
        leak_path = _find_internal_key_path(self.extensions)
        if leak_path:
            raise ValueError(
                "external trace extensions must not contain internal-only fields "
                f"(found {leak_path})"
            )
        return self


class ApiRequestPayload(SchemaModel):
    """Customer-visible API request trace."""

    request_id: NonEmptyStr
    method: HttpMethod
    route: NonEmptyStr
    request_size_bytes: Annotated[int, Field(ge=0)] | None = None


class ApiRequestTrace(ExternalTraceBase):
    """External trace for inbound API requests."""

    event_type: Literal["api_request"] = "api_request"
    payload: ApiRequestPayload


class ApiResponsePayload(SchemaModel):
    """Customer-visible API response trace."""

    request_id: NonEmptyStr
    status_code: Annotated[int, Field(ge=100, le=599)]
    latency_ms: Annotated[int, Field(ge=0)]
    response_size_bytes: Annotated[int, Field(ge=0)] | None = None
    cache_hit: bool | None = None


class ApiResponseTrace(ExternalTraceBase):
    """External trace for API response outcomes."""

    event_type: Literal["api_response"] = "api_response"
    payload: ApiResponsePayload


class BillingEventPayload(SchemaModel):
    """Billing event emitted to customer-visible ledgers."""

    billing_event_id: NonEmptyStr
    meter: NonEmptyStr
    quantity: Annotated[float, Field(ge=0)]
    unit: NonEmptyStr
    amount_usd: Annotated[float, Field(ge=0)]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] = "USD"
    billable: bool = True


class BillingEventTrace(ExternalTraceBase):
    """External trace for customer billing events."""

    event_type: Literal["billing_event"] = "billing_event"
    payload: BillingEventPayload


class PipelineStagePayload(SchemaModel):
    """Customer-visible pipeline stage state."""

    pipeline_run_id: NonEmptyStr
    stage: NonEmptyStr
    status: PipelineStatus
    visible_label: NonEmptyStr
    duration_ms: Annotated[int, Field(ge=0)] | None = None


class PipelineStageTrace(ExternalTraceBase):
    """External trace for visible execution pipeline stages."""

    event_type: Literal["pipeline_stage"] = "pipeline_stage"
    payload: PipelineStagePayload


InternalTrace = Annotated[
    AgentCoordinationTrace | InboxProtocolTrace | DispatchLifecycleTrace,
    Field(discriminator="event_type"),
]
ExternalTrace = Annotated[
    ApiRequestTrace | ApiResponseTrace | BillingEventTrace | PipelineStageTrace,
    Field(discriminator="event_type"),
]

_INTERNAL_TRACE_ADAPTER = TypeAdapter(InternalTrace)
_EXTERNAL_TRACE_ADAPTER = TypeAdapter(ExternalTrace)


def validate_internal_trace(payload: Mapping[str, Any]) -> AgentCoordinationTrace | InboxProtocolTrace | DispatchLifecycleTrace:
    """Validate a Python mapping as an internal trace event."""
    return _INTERNAL_TRACE_ADAPTER.validate_python(payload)


def validate_internal_trace_json(payload: str | bytes) -> AgentCoordinationTrace | InboxProtocolTrace | DispatchLifecycleTrace:
    """Validate a JSON document as an internal trace event."""
    return _INTERNAL_TRACE_ADAPTER.validate_json(payload)


def validate_external_trace(payload: Mapping[str, Any]) -> ApiRequestTrace | ApiResponseTrace | BillingEventTrace | PipelineStageTrace:
    """Validate a Python mapping as an external trace event."""
    return _EXTERNAL_TRACE_ADAPTER.validate_python(payload)


def validate_external_trace_json(payload: str | bytes) -> ApiRequestTrace | ApiResponseTrace | BillingEventTrace | PipelineStageTrace:
    """Validate a JSON document as an external trace event."""
    return _EXTERNAL_TRACE_ADAPTER.validate_json(payload)


def internal_trace_json_schema() -> dict[str, Any]:
    """Return the JSON Schema artifact for internal traces."""
    return _INTERNAL_TRACE_ADAPTER.json_schema()


def external_trace_json_schema() -> dict[str, Any]:
    """Return the JSON Schema artifact for external traces."""
    return _EXTERNAL_TRACE_ADAPTER.json_schema()
