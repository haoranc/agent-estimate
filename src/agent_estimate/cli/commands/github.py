"""GitHub command helpers."""

from __future__ import annotations

import re

_ISSUE_TOKEN_RE = re.compile(r"^\d+$")


def parse_issue_selection(value: str) -> list[int]:
    """Parse issue selection text into integer issue numbers.

    Accepts comma or whitespace separators, with optional leading '#'.
    Examples: "1,2,3", "#1 #2 #3", "1, #2 3".
    """
    if not value.strip():
        return []

    numbers: list[int] = []
    for raw_token in re.split(r"[,\s]+", value.strip()):
        token = raw_token.strip()
        if not token:
            continue
        if token.startswith("#"):
            token = token[1:]
        if not _ISSUE_TOKEN_RE.fullmatch(token):
            raise ValueError(f"Invalid issue token: {raw_token}")
        numbers.append(int(token))
    return numbers
