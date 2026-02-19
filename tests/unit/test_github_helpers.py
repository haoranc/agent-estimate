"""Tests for cli/commands/github.py helper functions."""

from __future__ import annotations

import pytest

from agent_estimate.cli.commands.github import parse_issue_selection


class TestParseIssueSelection:
    def test_valid_comma_separated(self) -> None:
        assert parse_issue_selection("1,2,3") == [1, 2, 3]

    def test_single_issue(self) -> None:
        assert parse_issue_selection("42") == [42]

    def test_empty_string_returns_empty_list(self) -> None:
        assert parse_issue_selection("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_issue_selection("   ") == []

    def test_values_with_surrounding_spaces(self) -> None:
        assert parse_issue_selection(" 1 , 2 , 3 ") == [1, 2, 3]

    def test_hash_prefixed_values_with_spaces(self) -> None:
        assert parse_issue_selection("#1 #2 #3") == [1, 2, 3]

    def test_mixed_commas_spaces_and_hash_prefix(self) -> None:
        assert parse_issue_selection("1, #2 3") == [1, 2, 3]

    def test_non_integer_token_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_issue_selection("1,two,3")

    def test_floating_point_token_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_issue_selection("1.5,2")

    def test_bare_hash_token_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_issue_selection("#,2")

    def test_empty_tokens_between_commas_ignored(self) -> None:
        # "1,,3" → strip(",") leaves empty middle, which is skipped by `if part.strip()`
        result = parse_issue_selection("1,,3")
        assert result == [1, 3]

    def test_trailing_comma_ignored(self) -> None:
        result = parse_issue_selection("1,2,")
        assert result == [1, 2]

    def test_large_issue_numbers(self) -> None:
        result = parse_issue_selection("1000,9999")
        assert result == [1000, 9999]
