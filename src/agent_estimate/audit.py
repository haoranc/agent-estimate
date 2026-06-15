"""Structured audit logging helpers."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}
_SENSITIVE_KEY_SEGMENTS = (
    "authorization",
    "cookie",
    "email",
    "password",
    "secret",
    "token",
)
_SENSITIVE_KEY_PAIRS = {
    ("access", "key"),
    ("api", "key"),
    ("private", "key"),
    ("refresh", "token"),
}
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]+"),
)
_EMAIL_PATTERN = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")
_MAX_STRING_LENGTH = 240

_audit_logger: "AuditLogger | None" = None
# Guards swaps of the process-global logger instance.
_audit_lock = RLock()


@dataclass(frozen=True)
class AuditConfig:
    """Runtime audit logging configuration."""

    enabled: bool
    level: str
    destination: str
    actor: str
    environment: str

    @classmethod
    def from_env(cls) -> "AuditConfig":
        enabled_raw = os.getenv("AGENT_ESTIMATE_AUDIT_ENABLED")
        destination = os.getenv("AGENT_ESTIMATE_AUDIT_DESTINATION", "").strip()
        enabled = _parse_bool(enabled_raw) if enabled_raw is not None else bool(destination)
        level = os.getenv("AGENT_ESTIMATE_AUDIT_LEVEL", "INFO").strip().upper() or "INFO"
        if level not in _LEVEL_ORDER:
            level = "INFO"
        if not destination:
            destination = "stderr"
        actor = os.getenv("AGENT_ESTIMATE_AUDIT_ACTOR", "agent-estimate").strip() or "agent-estimate"
        environment = os.getenv("AGENT_ESTIMATE_ENVIRONMENT", "local").strip() or "local"
        return cls(
            enabled=enabled,
            level=level,
            destination=destination,
            actor=actor,
            environment=environment,
        )


class AuditLogger:
    """Write scrubbed JSON events to a configured sink."""

    def __init__(self, config: AuditConfig) -> None:
        self._config = config
        # Serializes writes for this logger instance.
        self._lock = RLock()
        self._warned_stdout_redirect = False

    def emit(
        self,
        event_type: str,
        *,
        level: str = "INFO",
        outcome: str = "success",
        duration_ms: float | None = None,
        **details: Any,
    ) -> None:
        normalized_level = level.upper()
        if not self._config.enabled:
            return
        if _LEVEL_ORDER.get(normalized_level, 100) < _LEVEL_ORDER[self._config.level]:
            return

        event: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": uuid4().hex,
            "level": normalized_level,
            "event_type": event_type,
            "actor": self._config.actor,
            "environment": self._config.environment,
            "outcome": outcome,
            "details": _scrub(details),
        }
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms, 3)

        self._write_line(json.dumps(event, sort_keys=True))

    def _write_line(self, line: str) -> None:
        with self._lock:
            if self._config.destination == "stdout":
                if not self._warned_stdout_redirect:
                    print(
                        "Warning: AGENT_ESTIMATE_AUDIT_DESTINATION=stdout is deprecated; "
                        "writing audit events to stderr to preserve report stdout.",
                        file=sys.stderr,
                    )
                    self._warned_stdout_redirect = True
                print(line, file=sys.stderr)
                return
            if self._config.destination == "stderr":
                print(line, file=sys.stderr)
                return

            destination = Path(self._config.destination)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Reopen per write to keep the CLI logger stateless; revisit if a
                # long-lived service needs a persistent buffered handle.
                destination_fd = os.open(
                    destination,
                    os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(destination_fd, "a", encoding="utf-8") as handle:
                    handle.write(f"{line}\n")
            except OSError as exc:
                print(
                    f"Warning: failed to write audit log to {destination.name}: {exc}",
                    file=sys.stderr,
                )


def configure_audit_logger(config: AuditConfig | None = None) -> AuditLogger:
    """Configure the global audit logger."""
    global _audit_logger
    with _audit_lock:
        _audit_logger = AuditLogger(config or AuditConfig.from_env())
        return _audit_logger


def reset_audit_logger() -> None:
    """Reset the global audit logger so tests can reconfigure it."""
    global _audit_logger
    with _audit_lock:
        _audit_logger = None


def emit_audit_event(
    event_type: str,
    *,
    level: str = "INFO",
    outcome: str = "success",
    duration_ms: float | None = None,
    **details: Any,
) -> None:
    """Emit one structured audit event."""
    get_audit_logger().emit(
        event_type,
        level=level,
        outcome=outcome,
        duration_ms=duration_ms,
        **details,
    )


def get_audit_logger() -> AuditLogger:
    """Return the configured global audit logger."""
    global _audit_logger
    with _audit_lock:
        if _audit_logger is None:
            _audit_logger = AuditLogger(AuditConfig.from_env())
        return _audit_logger


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _scrub(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): _scrub(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_scrub(item) for item in value]
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        scrubbed = value
        for pattern in _SENSITIVE_VALUE_PATTERNS:
            scrubbed = pattern.sub("[REDACTED]", scrubbed)
        scrubbed = _EMAIL_PATTERN.sub("[REDACTED]", scrubbed)
        if len(scrubbed) > _MAX_STRING_LENGTH:
            scrubbed = f"{scrubbed[:_MAX_STRING_LENGTH]}..."
        return scrubbed
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).replace("-", "_").lower()
    segments = tuple(part for part in normalized.split("_") if part)
    if any(segment in _SENSITIVE_KEY_SEGMENTS for segment in segments):
        return True
    return any(pair in _SENSITIVE_KEY_PAIRS for pair in zip(segments, segments[1:]))
