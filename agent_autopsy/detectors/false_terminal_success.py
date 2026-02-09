"""False Terminal Success Detector.

Detects cases where:
- The trace reached a terminal/summarizer span
- Key content fields in the output are empty (e.g. summary="")
- The workflow status indicates "completed" but meaningful output is missing
- No explicit validation step exists

This detector looks at *content fields* within output dicts, not just whether
the dict itself is empty. A dict like {'summary': '', 'status': 'completed'}
is a false terminal success because the summary content is empty.
"""

import logging
from typing import Any

from agent_autopsy.core.models import (
    CanonicalTrace,
    DetectedFailure,
    FailureEvidence,
    Severity,
)
from agent_autopsy.detectors.base import FailureDetector
from agent_autopsy.utils.diffing import is_empty_output
from agent_autopsy.utils.ordering import find_terminal_spans, find_validation_spans

logger = logging.getLogger(__name__)

# Fields that carry actual content (not workflow metadata)
CONTENT_FIELDS = {"summary", "result", "answer", "output", "response", "report", "text", "content"}
# Fields that are workflow metadata (not content)
META_FIELDS = {"status", "retry_log", "query", "plan"}


class FalseTerminalSuccessDetector(FailureDetector):
    """Detects traces that appear successful but have missing or empty outputs."""

    @property
    def name(self) -> str:
        return "false_terminal_success"

    @property
    def description(self) -> str:
        return (
            "Detects when a trace reaches a terminal span but required "
            "output fields are missing or empty, with no validation step."
        )

    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        failures: list[DetectedFailure] = []
        terminal_spans = find_terminal_spans(trace)
        validation_spans = find_validation_spans(trace)
        has_validation = len(validation_spans) > 0

        # Check terminal span outputs for empty content fields
        for term_span in terminal_spans:
            span_failure = self._check_terminal_span(
                trace, term_span.span_id, term_span.name,
                term_span.output, term_span.has_error, has_validation,
            )
            if span_failure:
                failures.append(span_failure)

        # Check trace-level output for empty content fields
        trace_failure = self._check_trace_output(trace, has_validation)
        if trace_failure:
            failures.append(trace_failure)

        return failures

    def _check_trace_output(
        self, trace: CanonicalTrace, has_validation: bool
    ) -> DetectedFailure | None:
        """Check if the trace-level output has empty content fields."""
        has_errors = any(s.has_error for s in trace.spans)
        if has_errors:
            return None

        empty_fields = self._find_empty_content_fields(trace.output)
        if not empty_fields:
            # Also check if the entire output is empty
            if is_empty_output(trace.output):
                empty_fields = ["<entire output>"]
            else:
                return None

        evidence = [
            FailureEvidence(
                description=(
                    f"Trace completed without errors but content field(s) "
                    f"{empty_fields} are empty in the trace output."
                ),
                details={
                    "empty_content_fields": empty_fields,
                    "trace_output_preview": _preview(trace.output),
                    "total_spans": len(trace.spans),
                },
            )
        ]

        if not has_validation:
            evidence.append(
                FailureEvidence(
                    description="No validation step found to verify output completeness.",
                    details={"validation_spans_found": 0},
                )
            )

        return DetectedFailure(
            detector_name=self.name,
            failure_type="false_terminal_success",
            title="Trace completed successfully but content output is empty",
            severity=Severity.CRITICAL if not has_validation else Severity.HIGH,
            confidence=0.85 if not has_validation else 0.7,
            evidence=evidence,
        )

    def _check_terminal_span(
        self,
        trace: CanonicalTrace,
        span_id: str,
        span_name: str,
        span_output: object,
        has_error: bool,
        has_validation: bool,
    ) -> DetectedFailure | None:
        """Check if a terminal span has empty content fields."""
        if has_error:
            return None

        empty_fields = self._find_empty_content_fields(span_output)
        if not empty_fields:
            if is_empty_output(span_output):
                empty_fields = ["<entire output>"]
            else:
                return None

        evidence = [
            FailureEvidence(
                description=(
                    f"Terminal span '{span_name}' completed without error "
                    f"but content field(s) {empty_fields} are empty."
                ),
                span_ids=[span_id],
                details={
                    "empty_content_fields": empty_fields,
                    "span_output_preview": _preview(span_output),
                },
            )
        ]

        if not has_validation:
            evidence.append(
                FailureEvidence(
                    description=(
                        "No validation step exists to catch missing output "
                        "in terminal span."
                    ),
                    span_ids=[],
                    details={"validation_spans_found": 0},
                )
            )

        return DetectedFailure(
            detector_name=self.name,
            failure_type="false_terminal_success",
            title=f"Terminal span '{span_name}' succeeded with empty content",
            severity=Severity.HIGH if not has_validation else Severity.MEDIUM,
            confidence=0.75 if not has_validation else 0.6,
            evidence=evidence,
        )

    def _find_empty_content_fields(self, output: Any) -> list[str]:
        """Find content fields in a dict output that are empty."""
        if not isinstance(output, dict):
            return []

        empty = []
        for key, value in output.items():
            if key.lower() in CONTENT_FIELDS:
                if value is None or (isinstance(value, str) and not value.strip()):
                    empty.append(key)
                elif isinstance(value, (list, dict)) and len(value) == 0:
                    empty.append(key)
        return empty


def _preview(value: object, max_len: int = 200) -> str:
    """Create a truncated string preview of a value."""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
