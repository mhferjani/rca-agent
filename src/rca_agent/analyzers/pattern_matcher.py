"""Pattern matching for known error types."""

import re
from dataclasses import dataclass

from rca_agent.models.reports import ErrorCategory, Severity


@dataclass
class ErrorPattern:
    """Definition of an error pattern."""

    name: str
    category: ErrorCategory
    severity: Severity
    patterns: list[str]  # Regex patterns
    description: str
    recommendation: str


# Known error patterns with their signatures
ERROR_PATTERNS: list[ErrorPattern] = [
    # Resource exhaustion
    ErrorPattern(
        name="java_oom",
        category=ErrorCategory.RESOURCE_EXHAUSTION,
        severity=Severity.HIGH,
        patterns=[
            r"java\.lang\.OutOfMemoryError",
            r"Java heap space",
            r"GC overhead limit exceeded",
            r"Metaspace",
        ],
        description="Java process ran out of memory",
        recommendation="Increase executor memory or optimize data partitioning",
    ),
    ErrorPattern(
        name="python_oom",
        category=ErrorCategory.RESOURCE_EXHAUSTION,
        severity=Severity.HIGH,
        patterns=[
            r"MemoryError",
            r"Cannot allocate memory",
            r"killed.*OOM",
            r"OOMKilled",
        ],
        description="Python process ran out of memory",
        recommendation="Reduce batch size or increase container memory limits",
    ),
    ErrorPattern(
        name="disk_full",
        category=ErrorCategory.RESOURCE_EXHAUSTION,
        severity=Severity.CRITICAL,
        patterns=[
            r"No space left on device",
            r"Disk quota exceeded",
            r"ENOSPC",
        ],
        description="Disk space exhausted",
        recommendation="Clean up temporary files or increase disk allocation",
    ),
    ErrorPattern(
        name="timeout",
        category=ErrorCategory.RESOURCE_EXHAUSTION,
        severity=Severity.MEDIUM,
        patterns=[
            r"TimeoutError",
            r"timed out",
            r"deadline exceeded",
            r"execution timeout",
        ],
        description="Operation timed out",
        recommendation="Increase timeout or optimize the operation",
    ),
    # Schema issues
    ErrorPattern(
        name="column_not_found",
        category=ErrorCategory.SCHEMA_MISMATCH,
        severity=Severity.HIGH,
        patterns=[
            r"column.*not found",
            r"KeyError.*column",
            r"no such column",
            r"Unknown column",
            r"AnalysisException.*cannot resolve",
        ],
        description="Expected column not found in data",
        recommendation="Verify source schema and update transformation",
    ),
    ErrorPattern(
        name="type_mismatch",
        category=ErrorCategory.SCHEMA_MISMATCH,
        severity=Severity.MEDIUM,
        patterns=[
            r"cannot cast",
            r"type mismatch",
            r"invalid type",
            r"TypeError.*expected",
            r"cannot be converted to",
        ],
        description="Data type mismatch",
        recommendation="Add type casting or fix source data types",
    ),
    ErrorPattern(
        name="parse_error",
        category=ErrorCategory.SCHEMA_MISMATCH,
        severity=Severity.MEDIUM,
        patterns=[
            r"parse error",
            r"JSON.*invalid",
            r"malformed",
            r"unexpected token",
            r"XMLSyntaxError",
        ],
        description="Failed to parse input data",
        recommendation="Check source data format and parser configuration",
    ),
    # Source availability
    ErrorPattern(
        name="connection_refused",
        category=ErrorCategory.SOURCE_UNAVAILABLE,
        severity=Severity.HIGH,
        patterns=[
            r"Connection refused",
            r"ECONNREFUSED",
            r"Could not connect",
            r"Connection reset",
        ],
        description="Cannot connect to external service",
        recommendation="Check if the source service is running and accessible",
    ),
    ErrorPattern(
        name="http_5xx",
        category=ErrorCategory.SOURCE_UNAVAILABLE,
        severity=Severity.HIGH,
        patterns=[
            r"HTTP 5\d{2}",
            r"500 Internal Server Error",
            r"502 Bad Gateway",
            r"503 Service Unavailable",
            r"504 Gateway Timeout",
        ],
        description="External API returned server error",
        recommendation="Check external service status and retry",
    ),
    ErrorPattern(
        name="dns_failure",
        category=ErrorCategory.SOURCE_UNAVAILABLE,
        severity=Severity.HIGH,
        patterns=[
            r"Name or service not known",
            r"getaddrinfo failed",
            r"DNS resolution failed",
            r"NXDOMAIN",
        ],
        description="DNS resolution failed",
        recommendation="Check network configuration and DNS settings",
    ),
    # Data quality
    ErrorPattern(
        name="null_constraint",
        category=ErrorCategory.DATA_QUALITY,
        severity=Severity.MEDIUM,
        patterns=[
            r"NOT NULL constraint",
            r"null value in column.*violates",
            r"Cannot insert NULL",
        ],
        description="NULL value violates constraint",
        recommendation="Add NULL handling or fix source data",
    ),
    ErrorPattern(
        name="unique_violation",
        category=ErrorCategory.DATA_QUALITY,
        severity=Severity.MEDIUM,
        patterns=[
            r"unique constraint",
            r"duplicate key",
            r"IntegrityError.*UNIQUE",
        ],
        description="Duplicate key violation",
        recommendation="Add deduplication logic or use UPSERT",
    ),
    ErrorPattern(
        name="assertion_failed",
        category=ErrorCategory.DATA_QUALITY,
        severity=Severity.MEDIUM,
        patterns=[
            r"AssertionError",
            r"data quality check failed",
            r"expectation.*failed",
            r"Great Expectations.*failed",
        ],
        description="Data quality assertion failed",
        recommendation="Investigate data quality issue in source",
    ),
    # Permission errors
    ErrorPattern(
        name="auth_failure",
        category=ErrorCategory.PERMISSION_ERROR,
        severity=Severity.HIGH,
        patterns=[
            r"401 Unauthorized",
            r"403 Forbidden",
            r"Access Denied",
            r"PermissionDenied",
            r"authentication failed",
        ],
        description="Authentication or authorization failed",
        recommendation="Check credentials and permissions",
    ),
    ErrorPattern(
        name="token_expired",
        category=ErrorCategory.PERMISSION_ERROR,
        severity=Severity.MEDIUM,
        patterns=[
            r"token.*expired",
            r"JWT.*expired",
            r"session.*expired",
            r"credential.*expired",
        ],
        description="Authentication token expired",
        recommendation="Refresh authentication tokens",
    ),
    # Network errors
    ErrorPattern(
        name="ssl_error",
        category=ErrorCategory.NETWORK_ERROR,
        severity=Severity.HIGH,
        patterns=[
            r"SSL.*error",
            r"certificate verify failed",
            r"SSLError",
            r"CERTIFICATE_VERIFY_FAILED",
        ],
        description="SSL/TLS connection error",
        recommendation="Check SSL certificates and configuration",
    ),
]


class PatternMatcher:
    """Matches log content against known error patterns."""

    def __init__(self, patterns: list[ErrorPattern] | None = None) -> None:
        """Initialize pattern matcher.

        Args:
            patterns: Custom patterns to use (defaults to ERROR_PATTERNS)
        """
        self.patterns = patterns or ERROR_PATTERNS
        # Compile patterns for efficiency
        self._compiled = [
            (pattern, [re.compile(p, re.IGNORECASE) for p in pattern.patterns])
            for pattern in self.patterns
        ]

    def match(self, log_content: str) -> list[tuple[ErrorPattern, list[str]]]:
        """Find all matching patterns in log content.

        Args:
            log_content: Log text to analyze

        Returns:
            List of (pattern, matched_strings) tuples, sorted by severity
        """
        matches = []

        for pattern, compiled_regexes in self._compiled:
            matched_strings = []
            for regex in compiled_regexes:
                found = regex.findall(log_content)
                matched_strings.extend(found)

            if matched_strings:
                matches.append((pattern, matched_strings))

        # Sort by severity (critical first)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        matches.sort(key=lambda x: severity_order[x[0].severity])

        return matches

    def get_primary_error(self, log_content: str) -> tuple[ErrorPattern, list[str]] | None:
        """Get the most likely primary error pattern.

        Args:
            log_content: Log text to analyze

        Returns:
            Primary (pattern, matched_strings) or None
        """
        matches = self.match(log_content)
        return matches[0] if matches else None

    def extract_key_lines(
        self,
        log_content: str,
        max_lines: int = 10,
    ) -> list[str]:
        """Extract key lines that match error patterns.

        Args:
            log_content: Log text to analyze
            max_lines: Maximum lines to return

        Returns:
            List of key log lines
        """
        key_lines = []
        lines = log_content.split("\n")

        all_patterns = []
        for _, compiled_regexes in self._compiled:
            all_patterns.extend(compiled_regexes)

        for line in lines:
            for regex in all_patterns:
                if regex.search(line):
                    key_lines.append(line.strip())
                    break

            if len(key_lines) >= max_lines:
                break

        return key_lines
