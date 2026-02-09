"""Retry Without Learning Detector.

Detects cases where:
- The same span retried multiple times
- Inputs and outputs were identical across retries
- No corrective change occurred
"""

from agent_autopsy.core.models import (
    CanonicalTrace,
    DetectedFailure,
    FailureEvidence,
    Severity,
)
from agent_autopsy.detectors.base import FailureDetector
from agent_autopsy.utils.diffing import values_are_equivalent
from agent_autopsy.utils.ordering import find_retry_groups


class RetryWithoutLearningDetector(FailureDetector):
    """Detects retries that repeat identical inputs/outputs with no corrective change."""

    @property
    def name(self) -> str:
        return "retry_without_learning"

    @property
    def description(self) -> str:
        return (
            "Detects when a span retries multiple times with identical "
            "inputs and outputs, indicating no corrective action was taken."
        )

    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        failures: list[DetectedFailure] = []
        retry_groups = find_retry_groups(trace)

        for span_name, spans in retry_groups.items():
            if len(spans) < 2:
                continue

            identical_input_pairs = self._find_identical_pairs(
                spans, compare_field="input"
            )
            identical_output_pairs = self._find_identical_pairs(
                spans, compare_field="output"
            )

            # Both inputs AND outputs identical across consecutive retries
            identical_both = self._find_fully_identical_consecutive(spans)

            if not identical_both:
                continue

            evidence: list[FailureEvidence] = []

            evidence.append(
                FailureEvidence(
                    description=(
                        f"Span '{span_name}' retried {len(spans)} times. "
                        f"{len(identical_both)} consecutive pair(s) had identical "
                        f"inputs AND outputs, indicating no learning occurred."
                    ),
                    span_ids=[s.span_id for s in spans],
                    details={
                        "total_attempts": len(spans),
                        "identical_consecutive_pairs": len(identical_both),
                        "identical_input_pairs": len(identical_input_pairs),
                        "identical_output_pairs": len(identical_output_pairs),
                    },
                )
            )

            for pair in identical_both:
                span_a, span_b = pair
                evidence.append(
                    FailureEvidence(
                        description=(
                            f"Attempts {span_a.retry_index} and {span_b.retry_index} "
                            f"of '{span_name}' produced identical results."
                        ),
                        span_ids=[span_a.span_id, span_b.span_id],
                        details={
                            "input_preview": _preview(span_a.input),
                            "output_preview": _preview(span_a.output),
                        },
                    )
                )

            # Higher confidence with more identical retries
            confidence = min(0.95, 0.6 + 0.1 * len(identical_both))
            severity = (
                Severity.HIGH
                if len(identical_both) >= 2
                else Severity.MEDIUM
            )

            failures.append(
                DetectedFailure(
                    detector_name=self.name,
                    failure_type="retry_without_learning",
                    title=f"Retry without learning in '{span_name}'",
                    severity=severity,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        return failures

    def _find_identical_pairs(
        self, spans: list, compare_field: str
    ) -> list[tuple]:
        """Find consecutive span pairs with identical values for a given field."""
        pairs = []
        for i in range(len(spans) - 1):
            val_a = getattr(spans[i], compare_field)
            val_b = getattr(spans[i + 1], compare_field)
            if val_a is not None and val_b is not None:
                if values_are_equivalent(val_a, val_b):
                    pairs.append((spans[i], spans[i + 1]))
        return pairs

    def _find_fully_identical_consecutive(self, spans: list) -> list[tuple]:
        """Find consecutive pairs where both input AND output are identical."""
        pairs = []
        for i in range(len(spans) - 1):
            a, b = spans[i], spans[i + 1]
            inputs_match = (
                a.input is not None
                and b.input is not None
                and values_are_equivalent(a.input, b.input)
            )
            outputs_match = (
                a.output is not None
                and b.output is not None
                and values_are_equivalent(a.output, b.output)
            )
            # Count as identical if inputs match (outputs may both be None/error)
            if inputs_match and (outputs_match or (a.output is None and b.output is None)):
                pairs.append((a, b))
        return pairs


def _preview(value: object, max_len: int = 200) -> str:
    """Create a truncated string preview of a value."""
    text = str(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
