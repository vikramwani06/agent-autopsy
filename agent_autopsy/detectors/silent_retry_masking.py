"""Silent Retry Masking Detector.

Detects cases where:
- A span executed multiple times
- Earlier attempts failed or were incomplete
- A later retry succeeded
- No validation step caught state loss
"""

from agent_autopsy.core.models import (
    CanonicalTrace,
    DetectedFailure,
    FailureEvidence,
    Severity,
)
from agent_autopsy.detectors.base import FailureDetector
from agent_autopsy.utils.diffing import is_empty_output, values_are_equivalent
from agent_autopsy.utils.ordering import find_retry_groups, find_validation_spans


class SilentRetryMaskingDetector(FailureDetector):
    """Detects retries that silently mask earlier failures without validation."""

    @property
    def name(self) -> str:
        return "silent_retry_masking"

    @property
    def description(self) -> str:
        return (
            "Detects when a span retries after failure, succeeds, "
            "but no validation step verifies state consistency."
        )

    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        failures: list[DetectedFailure] = []
        retry_groups = find_retry_groups(trace)
        validation_spans = find_validation_spans(trace)
        has_validation = len(validation_spans) > 0

        for span_name, spans in retry_groups.items():
            if len(spans) < 2:
                continue

            earlier_attempts = spans[:-1]
            final_attempt = spans[-1]

            # Check if earlier attempts failed or were incomplete
            failed_earlier = [
                s for s in earlier_attempts
                if s.has_error or is_empty_output(s.output)
            ]

            if not failed_earlier:
                continue

            # Check if the final attempt succeeded
            final_succeeded = (
                not final_attempt.has_error
                and not is_empty_output(final_attempt.output)
            )

            if not final_succeeded:
                continue

            # This is a silent retry masking pattern
            evidence: list[FailureEvidence] = []

            evidence.append(
                FailureEvidence(
                    description=(
                        f"Span '{span_name}' executed {len(spans)} times. "
                        f"{len(failed_earlier)} earlier attempt(s) failed or were incomplete, "
                        f"but the final attempt succeeded."
                    ),
                    span_ids=[s.span_id for s in spans],
                    details={
                        "total_attempts": len(spans),
                        "failed_attempts": len(failed_earlier),
                        "failed_span_ids": [s.span_id for s in failed_earlier],
                        "final_span_id": final_attempt.span_id,
                    },
                )
            )

            # Check for state loss between failed and successful attempts
            for failed_span in failed_earlier:
                if failed_span.output and final_attempt.output:
                    if not values_are_equivalent(
                        failed_span.output, final_attempt.output
                    ):
                        evidence.append(
                            FailureEvidence(
                                description=(
                                    f"Output differs between failed attempt "
                                    f"and successful retry of '{span_name}', "
                                    f"indicating potential state loss."
                                ),
                                span_ids=[
                                    failed_span.span_id,
                                    final_attempt.span_id,
                                ],
                                details={
                                    "failed_output_preview": _preview(
                                        failed_span.output
                                    ),
                                    "final_output_preview": _preview(
                                        final_attempt.output
                                    ),
                                },
                            )
                        )

            if not has_validation:
                evidence.append(
                    FailureEvidence(
                        description=(
                            "No validation step found in the trace to verify "
                            "state consistency after retry."
                        ),
                        span_ids=[],
                        details={"validation_spans_found": 0},
                    )
                )

            severity = Severity.HIGH if not has_validation else Severity.MEDIUM
            confidence = 0.8 if not has_validation else 0.6

            failures.append(
                DetectedFailure(
                    detector_name=self.name,
                    failure_type="silent_retry_masking",
                    title=f"Silent retry masking in '{span_name}'",
                    severity=severity,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        return failures


def _preview(value: object, max_len: int = 200) -> str:
    """Create a truncated string preview of a value."""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
