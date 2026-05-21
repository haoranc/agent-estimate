"""Unit tests for audit logger hardening."""

from __future__ import annotations

from pathlib import Path

from agent_estimate.audit import AuditConfig, AuditLogger, _scrub


def test_audit_logger_creates_owner_only_log_file(tmp_path: Path) -> None:
    audit_log = tmp_path / "audit.jsonl"
    logger = AuditLogger(
        AuditConfig(
            enabled=True,
            level="INFO",
            destination=str(audit_log),
            actor="test-agent",
            environment="test",
        ),
    )

    logger.emit("authentication_event", provider="gh")

    assert audit_log.exists()
    assert audit_log.stat().st_mode & 0o777 == 0o600


def test_scrub_uses_segment_aware_sensitive_key_detection() -> None:
    scrubbed = _scrub(
        {
            "monkey_key_phase": 42,
            "api_key": "secret",
            "privateKey": "secret",
            "plain_token": "secret",
        },
    )

    assert scrubbed["monkey_key_phase"] == 42
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["privateKey"] == "[REDACTED]"
    assert scrubbed["plain_token"] == "[REDACTED]"
