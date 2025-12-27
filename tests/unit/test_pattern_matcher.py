"""Tests for the pattern matcher."""

import pytest

from rca_agent.analyzers.pattern_matcher import PatternMatcher
from rca_agent.models.reports import ErrorCategory, Severity


class TestPatternMatcher:
    """Tests for PatternMatcher class."""

    @pytest.fixture
    def matcher(self) -> PatternMatcher:
        """Create a PatternMatcher instance."""
        return PatternMatcher()

    def test_match_oom_error(self, matcher: PatternMatcher) -> None:
        """Test matching OOM errors."""
        log_content = """
        [2024-01-15 10:28:00] ERROR: java.lang.OutOfMemoryError: Java heap space
            at java.util.Arrays.copyOf(Arrays.java:3236)
        """
        matches = matcher.match(log_content)

        assert len(matches) > 0
        pattern, matched_strings = matches[0]
        assert pattern.category == ErrorCategory.RESOURCE_EXHAUSTION
        assert "OutOfMemoryError" in matched_strings[0]

    def test_match_schema_error(self, matcher: PatternMatcher) -> None:
        """Test matching schema errors."""
        log_content = """
        [2024-01-15 10:00:00] KeyError: column 'customer_id' not found
        """
        matches = matcher.match(log_content)

        assert len(matches) > 0
        found_schema = any(m[0].category == ErrorCategory.SCHEMA_MISMATCH for m in matches)
        assert found_schema

    def test_match_connection_error(self, matcher: PatternMatcher) -> None:
        """Test matching connection errors."""
        log_content = """
        [2024-01-15 10:00:00] Connection refused to database:5432
        """
        matches = matcher.match(log_content)

        assert len(matches) > 0
        pattern, _ = matches[0]
        assert pattern.category == ErrorCategory.SOURCE_UNAVAILABLE

    def test_match_permission_error(self, matcher: PatternMatcher) -> None:
        """Test matching permission errors."""
        log_content = """
        [2024-01-15 10:00:00] HTTP 403 Forbidden - Access Denied
        """
        matches = matcher.match(log_content)

        assert len(matches) > 0
        pattern, _ = matches[0]
        assert pattern.category == ErrorCategory.PERMISSION_ERROR

    def test_match_multiple_errors(self, matcher: PatternMatcher) -> None:
        """Test matching multiple error types."""
        log_content = """
        [2024-01-15 10:00:00] Connection refused
        [2024-01-15 10:00:05] Retry 1/3
        [2024-01-15 10:00:10] java.lang.OutOfMemoryError: heap space
        """
        matches = matcher.match(log_content)

        # Should match both connection and OOM
        assert len(matches) >= 2

        categories = {m[0].category for m in matches}
        assert ErrorCategory.SOURCE_UNAVAILABLE in categories
        assert ErrorCategory.RESOURCE_EXHAUSTION in categories

    def test_no_match(self, matcher: PatternMatcher) -> None:
        """Test when no patterns match."""
        log_content = """
        [2024-01-15 10:00:00] Everything is fine
        [2024-01-15 10:00:01] Task completed successfully
        """
        matches = matcher.match(log_content)

        assert len(matches) == 0

    def test_get_primary_error(self, matcher: PatternMatcher) -> None:
        """Test getting the primary error."""
        log_content = """
        [2024-01-15 10:00:00] java.lang.OutOfMemoryError: heap space
        """
        result = matcher.get_primary_error(log_content)

        assert result is not None
        pattern, matches = result
        assert pattern.severity in [Severity.CRITICAL, Severity.HIGH]

    def test_extract_key_lines(self, matcher: PatternMatcher) -> None:
        """Test extracting key log lines."""
        log_content = """
[2024-01-15 10:00:00] Starting task
[2024-01-15 10:00:01] Processing data
[2024-01-15 10:00:02] ERROR: OutOfMemoryError
[2024-01-15 10:00:03] Task failed
[2024-01-15 10:00:04] Cleanup complete
        """
        key_lines = matcher.extract_key_lines(log_content)

        assert len(key_lines) > 0
        assert any("OutOfMemoryError" in line for line in key_lines)

    def test_case_insensitive_matching(self, matcher: PatternMatcher) -> None:
        """Test that matching is case insensitive."""
        log_content = "OUTOFMEMORYERROR: heap space"
        matches = matcher.match(log_content)

        assert len(matches) > 0
