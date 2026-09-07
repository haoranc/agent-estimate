"""Typed artifact boundaries for the v0.8 forecast contract.

These models validate data and replay declared cap arithmetic. Identity
generation, persistence, and outcome ingestion belong to their later consumers.
Identifiers here are caller-owned opaque strings; no identity is inferred.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal, localcontext
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
Identifier = Annotated[NonEmptyStr, StringConstraints(max_length=200)]
Count = Annotated[int, Field(strict=True, ge=0)]
Minutes = Annotated[float, Field(strict=True, ge=0)]
PositiveNumber = Annotated[float, Field(strict=True, gt=0)]


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_as_utc)]

TaskKind = Literal[
    "coding", "brainstorm", "research", "config", "documentation", "frontend", "app_dev"
]
ContextState = Literal["cold", "project_warm", "task_warm"]


class ContractModel(BaseModel):
    """Frozen records with finite numbers, including nested contract records.

    Collections are tuples in memory and arrays on the wire. To revise a record,
    validate a revised serialized mapping instead of mutating accepted inputs.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class SourceReference(ContractModel):
    """Optional caller-supplied source provenance; does not resolve external data."""

    system: NonEmptyStr | None = None
    record_id: NonEmptyStr | None = None
    revision: NonEmptyStr | None = None


class TaskScope(ContractModel):
    """Honest scope hints about the work, independent of admission caps."""

    expected_files_touched: Count | None = None
    estimated_lines_changed: Count | None = None
    estimated_tests: Count | None = None
    concerns: Count | None = None


class TaskSpec(ContractModel):
    """Task facts that remain true when the executor changes."""

    schema_version: Literal["agent-estimate/task-spec/v1"]
    task_id: Identifier
    title: NonEmptyStr
    description: NonEmptyStr
    task_type: TaskKind
    required_capabilities: tuple[NonEmptyStr, ...]
    dependency_task_ids: tuple[Identifier, ...]
    source: SourceReference | None = None
    scope: TaskScope = Field(default_factory=TaskScope)
    tags: tuple[NonEmptyStr, ...] = ()

    @field_validator("required_capabilities", "dependency_task_ids")
    @classmethod
    def reject_duplicates(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Do not silently discard duplicated capability or dependency entries."""
        if len(values) != len(set(values)):
            raise ValueError("entries must be unique")
        return values


class RuntimeIdentity(ContractModel):
    """The intended runtime and agent, without inferring a model from either."""

    name: NonEmptyStr
    agent_name: NonEmptyStr


class ModelIdentity(ContractModel):
    """Exactly one model identifier or explicit explanation of missing identity."""

    id: NonEmptyStr | None = None
    unknown_reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def require_identity_or_reason(self) -> ModelIdentity:
        if (self.id is None) == (self.unknown_reason is None):
            raise ValueError("model requires exactly one of id or unknown_reason")
        return self


class ConfigProfile(ContractModel):
    """Named, versioned configuration provenance, without loading configuration."""

    name: NonEmptyStr
    revision: NonEmptyStr


class ExecutionContext(ContractModel):
    """Context identity and whether its implicit co-dispatch reduction is requested.

    ``implicit_co_dispatch`` requests the existing 0.5x warm-context reduction
    for this ``context_key``. It is false for the first task in a group and when
    an explicit modifier owns warmth. Merely selecting co-dispatch is not a
    request to apply the reduction. No planner behavior is changed here.
    """

    state: ContextState
    context_key: NonEmptyStr | None = None
    basis: NonEmptyStr | None = None
    implicit_co_dispatch: Annotated[bool, Field(strict=True)] = False


class ExecutionModifiers(ContractModel):
    """Explicit engine factors; absent warmth is distinct from an explicit 1.0."""

    spec_clarity: Annotated[float, Field(strict=True, ge=0.3, le=1.3)] = 1.0
    warm_context: Annotated[float, Field(strict=True, ge=0.3, le=1.15)] | None = None
    agent_fit: Annotated[float, Field(strict=True, ge=0.9, le=1.2)] = 1.0


class ReviewPlan(ContractModel):
    """Execution review intent, independent of admission headroom arithmetic."""

    mode: Literal["none", "single_round", "review_loop"]
    expected_rounds: Count
    intensity: Literal["standard", "complex"]

    @model_validator(mode="after")
    def require_consistent_review(self) -> ReviewPlan:
        if self.mode == "none" and (self.expected_rounds != 0 or self.intensity != "standard"):
            raise ValueError("review mode none requires zero rounds and standard intensity")
        if self.mode == "single_round" and self.expected_rounds != 1:
            raise ValueError("single_round review requires exactly one round")
        if self.mode == "review_loop" and self.expected_rounds < 1:
            raise ValueError("review_loop requires at least one round")
        return self


class ExecutionProfile(ContractModel):
    """Planned execution facts, including the sole owner of context identity."""

    schema_version: Literal["agent-estimate/execution-profile/v1"]
    execution_profile_id: Identifier
    runtime: RuntimeIdentity
    model: ModelIdentity
    config_profile: ConfigProfile
    context: ExecutionContext
    review: ReviewPlan
    execution_mode: Literal["single", "parallel", "co_dispatch"]
    estimate_multiplier: PositiveNumber = 1.0
    reasoning_effort: NonEmptyStr | None = None
    modifiers: ExecutionModifiers = Field(default_factory=ExecutionModifiers)

    @model_validator(mode="after")
    def reject_double_counted_context(self) -> ExecutionProfile:
        """R6: explicit warmth wins; reject requests also relying on implicit warmth."""
        if self.context.implicit_co_dispatch:
            if self.execution_mode != "co_dispatch" or self.context.context_key is None:
                raise ValueError("implicit co-dispatch requires co_dispatch mode and context_key")
            if self.modifiers.warm_context is not None:
                raise ValueError(
                    "explicit warm_context wins for this context_key; "
                    "disable implicit_co_dispatch to avoid double counting"
                )
        return self


class CapFactor(ContractModel):
    """One ordered policy multiplier; review rounds never scale expected work."""

    name: Literal["rounds", "headroom"]
    value: PositiveNumber


class CapCalculation(ContractModel):
    """Replayable cap: multiply in order, then round once at the end.

    Decimal arithmetic avoids rounding an exact multiple up due to binary
    floating-point noise. Every intermediate and the result must remain finite.
    Values are minutes or file counts according to ``base_field``.
    """

    base_field: Literal["expected_minutes", "expected_files_touched"]
    base_value: Minutes
    factors: tuple[CapFactor, ...]
    rounding: Literal["none", "ceil"]
    rounding_increment: PositiveNumber = 1.0
    result: Minutes

    def replay(self) -> float:
        with localcontext() as context:
            context.prec = 50
            value = Decimal(str(self.base_value))
            for factor in self.factors:
                value *= Decimal(str(factor.value))
                if not math.isfinite(float(value)):
                    raise ValueError("cap arithmetic overflowed")
            if self.rounding == "ceil":
                step = Decimal(str(self.rounding_increment))
                value = (value / step).to_integral_value(rounding=ROUND_CEILING) * step
            result = float(value)
        if not math.isfinite(result):
            raise ValueError("cap arithmetic overflowed")
        return result

    @model_validator(mode="after")
    def require_replay(self) -> CapCalculation:
        if self.replay() != self.result:
            raise ValueError("cap result must equal replayed factors and rounding")
        return self


class AdmissionEnvelope(ContractModel):
    """R5: admission metadata only; declared caps are never scoring inputs.

    Bare caps remain valid metadata. When arithmetic is supplied it must replay
    to its cap on the matching axis; no expected duration is inferred from it.
    """

    schema_version: Literal["agent-estimate/admission-envelope/v1"]
    declared_cap_minutes: PositiveNumber | None = None
    declared_cap_files_touched: Count | None = None
    source: SourceReference | None = None
    minutes_calculation: CapCalculation | None = None
    files_calculation: CapCalculation | None = None

    @model_validator(mode="after")
    def require_matching_caps(self) -> AdmissionEnvelope:
        for calculation, field, cap in (
            (self.minutes_calculation, "expected_minutes", self.declared_cap_minutes),
            (self.files_calculation, "expected_files_touched", self.declared_cap_files_touched),
        ):
            if calculation is not None:
                if calculation.base_field != field or calculation.result != cap:
                    raise ValueError("cap calculation must match its axis and declared cap")
                if field == "expected_files_touched" and not calculation.base_value.is_integer():
                    raise ValueError("expected file count must be an integer")
        return self


TOKEN_POPULATION_WARNING = (
    "Population mismatch warning: this caller-supplied local-policy prior may not match "
    "this task and execution profile; it is not calibrated. PR-leg totals cannot be "
    "divided into task-level evidence."
)


class TokenForecast(ContractModel):
    """Independent token counts and their evidence; no implied rate or calibration.

    Total means processed tokens including cache carry. Output is reported
    separately and is included in total when both counts are supplied.
    """

    expected_tokens_total: Count | None = None
    expected_tokens_output: Count | None = None
    basis: Literal["unavailable", "local-policy"] = "unavailable"
    source: NonEmptyStr | None = None
    as_of: date | None = None
    population: NonEmptyStr | None = None
    warnings: tuple[NonEmptyStr, ...] = ()

    @field_validator("as_of", mode="before")
    @classmethod
    def require_calendar_date(cls, value: object) -> object:
        if value is None or type(value) is date:
            return value
        if isinstance(value, str) and len(value) == 10:
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                pass
            else:
                if parsed.isoformat() == value:
                    return parsed
        raise ValueError("token as_of must be a date in YYYY-MM-DD format")

    @model_validator(mode="after")
    def require_token_evidence(self) -> TokenForecast:
        total, output = self.expected_tokens_total, self.expected_tokens_output
        if total is not None and output is not None and output > total:
            raise ValueError("expected token output cannot exceed total processed tokens")
        if self.basis == "unavailable":
            if any(value is not None for value in (total, output, self.source, self.as_of,
                                                   self.population)) or self.warnings:
                raise ValueError("unavailable token forecasts require null counts and provenance")
        else:
            if total is None and output is None:
                raise ValueError("local-policy token forecasts require at least one token count")
            if self.source is None or self.as_of is None or self.population is None:
                raise ValueError("local-policy token forecasts require source, as_of and population")
            # All local priors carry the warning, including deserialized records.
            # A caller cannot claim calibrated task evidence or suppress this label.
            if self.warnings != (TOKEN_POPULATION_WARNING,):
                raise ValueError("local-policy token forecasts require the population mismatch warning")
        return self


class LocalTokenPrior(TokenForecast):
    """Explicit caller opt-in; no numbers or populations are supplied by the package."""

    basis: Literal["local-policy"]
    source: NonEmptyStr
    as_of: date
    population: NonEmptyStr
    warnings: tuple[NonEmptyStr, ...] = (TOKEN_POPULATION_WARNING,)


class EstimateRequest(ContractModel):
    """One task, one execution profile, and its separate admission block."""

    schema_version: Literal["agent-estimate/estimate-request/v1"]
    task_spec: TaskSpec
    execution_profile: ExecutionProfile
    admission: AdmissionEnvelope
    request_id: Identifier | None = None
    token_prior: LocalTokenPrior | None = None


class EngineProvenance(ContractModel):
    """Caller-supplied engine provenance for an emitted forecast record."""

    name: Literal["agent-estimate"] = "agent-estimate"
    version: NonEmptyStr
    registry_version: NonEmptyStr


class ForecastRecord(ContractModel):
    """Expected wall minutes are the sole scoring basis, independent of caps.

    Expected wall includes additive review; file expectations remain independent
    of file caps. Nullable fields allow reading earlier scaffold records, which
    are unscorable until an expected value is supplied. Source and date describe
    the forecast's evidence, never the reliability-threshold registry.
    """

    schema_version: Literal["agent-estimate/forecast/v1"]
    request: EstimateRequest
    created_at_utc: UtcDatetime
    engine: EngineProvenance
    forecast_id: Identifier | None = None
    expected_minutes: PositiveNumber | None = None
    expected_files_touched: Count | None = None
    expected_review_minutes: Minutes | None = None
    basis: Literal["expected-wall"] = "expected-wall"
    source: NonEmptyStr | None = None
    as_of: date | None = None
    tokens: TokenForecast = Field(default_factory=TokenForecast)

    @model_validator(mode="after")
    def require_expected_bases(self) -> ForecastRecord:
        if (self.expected_minutes is not None and self.expected_review_minutes is not None
                and self.expected_review_minutes > self.expected_minutes):
            raise ValueError("expected review cannot exceed expected wall minutes")
        for calculation, expected in (
            (self.request.admission.minutes_calculation, self.expected_minutes),
            (self.request.admission.files_calculation, self.expected_files_touched),
        ):
            if calculation is not None and calculation.base_value != expected:
                raise ValueError("cap calculation base must match the independent expected value")
        return self


class ObservedTokens(ContractModel):
    """Nullable v0.9 actuals slots; no token ingestion in this module."""

    tokens_total: Count | None = None
    tokens_output: Count | None = None
    total_definition: NonEmptyStr | None = None
    coverage: Literal["complete", "partial", "unavailable"] | None = None


class ObservationCensoring(ContractModel):
    """Unknown observation boundaries stay null instead of asserting coverage."""

    admission_pause_excluded: Annotated[bool, Field(strict=True)] | None = None
    peer_wait_included: Annotated[bool, Field(strict=True)] | None = None
    parallel_work_possible: Annotated[bool, Field(strict=True)] | None = None


class ObservedActuals(ContractModel):
    """Nullable outcome slots reserved for v0.9; no scoring or time derivation."""

    wall_minutes: Minutes | None = None
    work_minutes: Minutes | None = None
    total_minutes: Minutes | None = None
    time_basis: NonEmptyStr | None = None
    files_touched: Count | None = None
    review_rounds: Count | None = None
    tokens: ObservedTokens = Field(default_factory=ObservedTokens)
    started_at_utc: UtcDatetime | None = None
    completed_at_utc: UtcDatetime | None = None
    censoring: ObservationCensoring = Field(default_factory=ObservationCensoring)


class OutcomeObservation(ContractModel):
    """Outcome envelope with nullable future evidence and caller-supplied links."""

    schema_version: Literal["agent-estimate/outcome-observation/v1"]
    task_id: Identifier
    observation_id: Identifier | None = None
    forecast_id: Identifier | None = None
    execution_profile_id: Identifier | None = None
    execution_id: Identifier | None = None
    source: SourceReference | None = None
    actual: ObservedActuals = Field(default_factory=ObservedActuals)
