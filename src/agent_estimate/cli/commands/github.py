"""GitHub command helpers (stub)."""


def parse_issue_selection(value: str) -> list[int]:
    """Parse a comma-separated issue list into integers.

    Placeholder until GitHub issue ingestion is implemented.
    """
    if not value.strip():
        return []
    return [int(part.strip()) for part in value.split(",") if part.strip()]
