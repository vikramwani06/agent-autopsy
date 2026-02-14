"""Wrong Tool Usage Detector.

Detects cases where:
- Tool calls are flagged with correct_usage=false in the trace data
- Tools were used for a purpose different from what was needed
- The trace output contains tool_calls with semantic misuse indicators
- A span is explicitly named to indicate wrong behavior (e.g. 'wrong_inference')

This detector examines structured tool call metadata and span naming
conventions to identify cases where the agent selected the wrong tool
for the task, producing a semantically incorrect result even though
the workflow completed without errors.
"""

import json
import logging
from typing import Any

from agent_autopsy.core.models import (
    CanonicalTrace,
    CanonicalSpan,
    DetectedFailure,
    FailureEvidence,
    Severity,
)
from agent_autopsy.detectors.base import FailureDetector

logger = logging.getLogger(__name__)

# Span name patterns that indicate semantic errors
WRONG_BEHAVIOR_KEYWORDS = {
    "wrong", "incorrect", "invalid", "bad", "error_prone",
    "misinterpret", "hallucin", "confus", "misuse",
}


class WrongToolUsageDetector(FailureDetector):
    """Detects when the agent used the wrong tool for the task."""

    @property
    def name(self) -> str:
        return "wrong_tool_usage"

    @property
    def description(self) -> str:
        return (
            "Detects when tool calls are semantically incorrect — the wrong "
            "tool was selected for the task, or tool results were misinterpreted, "
            "producing a confidently wrong answer."
        )

    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        failures: list[DetectedFailure] = []

        # Strategy 1: Check tool_calls with correct_usage=false in span outputs
        tool_misuse_evidence = self._check_tool_call_metadata(trace)
        if tool_misuse_evidence:
            confidence = min(0.95, 0.7 + 0.05 * len(tool_misuse_evidence))
            failures.append(
                DetectedFailure(
                    detector_name=self.name,
                    failure_type="wrong_tool_usage",
                    title="Agent used the wrong tool for the task",
                    severity=Severity.CRITICAL,
                    confidence=confidence,
                    evidence=tool_misuse_evidence,
                )
            )

        # Strategy 2: Check for spans named with wrong-behavior keywords
        wrong_span_evidence = self._check_wrong_behavior_spans(trace)
        if wrong_span_evidence:
            failures.append(
                DetectedFailure(
                    detector_name=self.name,
                    failure_type="wrong_tool_usage",
                    title="Workflow contains semantically incorrect reasoning step",
                    severity=Severity.HIGH,
                    confidence=0.85,
                    evidence=wrong_span_evidence,
                )
            )

        # Strategy 3: Check trace-level output for tool misuse signals
        trace_level_evidence = self._check_trace_output_tool_calls(trace)
        if trace_level_evidence and not tool_misuse_evidence:
            confidence = min(0.95, 0.7 + 0.05 * len(trace_level_evidence))
            failures.append(
                DetectedFailure(
                    detector_name=self.name,
                    failure_type="wrong_tool_usage",
                    title="Trace output indicates wrong tool selection",
                    severity=Severity.CRITICAL,
                    confidence=confidence,
                    evidence=trace_level_evidence,
                )
            )

        return failures

    def _check_tool_call_metadata(self, trace: CanonicalTrace) -> list[FailureEvidence]:
        """Check span outputs for tool_calls with correct_usage=false."""
        evidence: list[FailureEvidence] = []

        for span in trace.spans:
            tool_calls = self._extract_tool_calls(span.output)
            wrong_calls = [
                tc for tc in tool_calls
                if tc.get("correct_usage") is False
            ]

            if not wrong_calls:
                continue

            for tc in wrong_calls:
                tool_name = tc.get("tool", "unknown")
                actual_purpose = tc.get("actual_purpose", "")
                tool_input = tc.get("input", "")
                tool_output = tc.get("output", "")

                desc_parts = [
                    f"Tool '{tool_name}' was used incorrectly in span '{span.name}'.",
                ]
                if actual_purpose:
                    desc_parts.append(f"The correct action: {actual_purpose}.")
                if tool_output and "error" in str(tool_output).lower():
                    desc_parts.append(f"The tool returned an error: {str(tool_output)[:150]}.")

                evidence.append(
                    FailureEvidence(
                        description=" ".join(desc_parts),
                        span_ids=[span.span_id],
                        details={
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "tool_output": str(tool_output)[:300],
                            "correct_usage": False,
                            "actual_purpose": actual_purpose,
                            "span_name": span.name,
                        },
                    )
                )

        return evidence

    def _check_wrong_behavior_spans(self, trace: CanonicalTrace) -> list[FailureEvidence]:
        """Check for spans whose names indicate wrong behavior."""
        evidence: list[FailureEvidence] = []

        for span in trace.spans:
            name_lower = span.name.lower()
            matched_keywords = [
                kw for kw in WRONG_BEHAVIOR_KEYWORDS
                if kw in name_lower
            ]
            if not matched_keywords:
                continue

            desc = (
                f"Span '{span.name}' indicates a semantically incorrect step "
                f"in the workflow (matched: {', '.join(matched_keywords)})."
            )

            details: dict[str, Any] = {
                "span_name": span.name,
                "span_type": span.span_type,
                "matched_keywords": matched_keywords,
            }

            # Extract reasoning from the span output if available
            if isinstance(span.output, dict):
                reasoning = span.output.get("reasoning", [])
                if reasoning:
                    details["reasoning"] = reasoning[:5] if isinstance(reasoning, list) else str(reasoning)[:300]
                inference = span.output.get("analysis", {}).get("inference", {})
                if inference:
                    details["inference"] = inference

            evidence.append(
                FailureEvidence(
                    description=desc,
                    span_ids=[span.span_id],
                    details=details,
                )
            )

        return evidence

    def _check_trace_output_tool_calls(self, trace: CanonicalTrace) -> list[FailureEvidence]:
        """Check trace-level output for tool_calls with misuse signals."""
        evidence: list[FailureEvidence] = []

        if not isinstance(trace.output, dict):
            return evidence

        tool_calls = trace.output.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            return evidence

        wrong_calls = [
            tc for tc in tool_calls
            if isinstance(tc, dict) and tc.get("correct_usage") is False
        ]

        for tc in wrong_calls:
            tool_name = tc.get("tool", "unknown")
            actual_purpose = tc.get("actual_purpose", "")
            tool_input = tc.get("input", "")
            tool_output = tc.get("output", "")

            desc_parts = [
                f"Trace output shows tool '{tool_name}' was used incorrectly.",
            ]
            if actual_purpose:
                desc_parts.append(f"Correct action: {actual_purpose}.")

            evidence.append(
                FailureEvidence(
                    description=" ".join(desc_parts),
                    span_ids=[],
                    details={
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_output": str(tool_output)[:300],
                        "correct_usage": False,
                        "actual_purpose": actual_purpose,
                    },
                )
            )

        return evidence

    def _extract_tool_calls(self, output: Any) -> list[dict[str, Any]]:
        """Extract tool_calls list from a span output."""
        if not isinstance(output, dict):
            return []
        tool_calls = output.get("tool_calls", [])
        if isinstance(tool_calls, list):
            return [tc for tc in tool_calls if isinstance(tc, dict)]
        return []
