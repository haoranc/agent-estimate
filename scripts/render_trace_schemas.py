"""Render checked-in JSON Schema artifacts for trace validation."""

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    from agent_estimate.tracing.schema import external_trace_json_schema, internal_trace_json_schema

    schema_root = ROOT / "schemas" / "trace"
    _write(schema_root / "internal_trace.schema.json", internal_trace_json_schema())
    _write(schema_root / "external_trace.schema.json", external_trace_json_schema())


if __name__ == "__main__":
    main()
