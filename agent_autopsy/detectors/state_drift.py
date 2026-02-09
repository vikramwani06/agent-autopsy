"""State Drift Detector.

Detects cases where:
- An early planning or intent span establishes what should be researched
- A later execution span (researcher) actually researches different topics
- The semantic content of the research does not match the plan's intent

This detector compares the *semantic content* of the plan (required_facts,
tools_to_use) against the actual tool calls and research results produced
by execution spans, rather than comparing structural dict keys or status fields.
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
from agent_autopsy.utils.ordering import find_planning_spans

logger = logging.getLogger(__name__)

# Fields that naturally change during workflow progression (not drift)
WORKFLOW_STATUS_FIELDS = {"status", "retry_log"}


class StateDriftDetector(FailureDetector):
    """Detects semantic drift between planning intent and execution results."""

    @property
    def name(self) -> str:
        return "state_drift"

    @property
    def description(self) -> str:
        return (
            "Detects when execution results diverge from the intent "
            "established in planning spans."
        )

    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        failures: list[DetectedFailure] = []

        planning_spans = find_planning_spans(trace)
        if not planning_spans:
            return failures

        # Find execution spans (researcher, executor, etc.)
        execution_spans = self._find_execution_spans(trace)
        if not execution_spans:
            return failures

        for plan_span in planning_spans:
            plan_data = self._extract_plan(plan_span)
            if not plan_data:
                continue

            for exec_span in execution_spans:
                evidence = self._compare_plan_to_execution(
                    plan_span, plan_data, exec_span, trace
                )
                if evidence:
                    confidence = min(0.9, 0.5 + 0.1 * len(evidence))
                    failures.append(
                        DetectedFailure(
                            detector_name=self.name,
                            failure_type="state_drift",
                            title=(
                                f"Execution in '{exec_span.name}' drifted from "
                                f"plan in '{plan_span.name}'"
                            ),
                            severity=Severity.HIGH,
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )

        return failures

    def _find_execution_spans(self, trace: CanonicalTrace) -> list[CanonicalSpan]:
        """Find spans that represent execution/research steps."""
        exec_keywords = {
            "research", "execut", "worker", "agent", "process",
            "fetch", "gather", "collect", "run", "perform",
        }
        result = []
        for span in trace.spans:
            name_lower = span.name.lower()
            if any(kw in name_lower for kw in exec_keywords):
                result.append(span)
        return result

    def _extract_plan(self, plan_span: CanonicalSpan) -> dict[str, Any] | None:
        """Extract structured plan data from a planning span's output."""
        output = plan_span.output
        if not output:
            return None

        if isinstance(output, dict):
            # LangGraph chains output state dicts — look for 'plan' key
            plan = output.get("plan", output)
            if isinstance(plan, dict) and (
                "required_facts" in plan
                or "tools_to_use" in plan
                or "objective" in plan
            ):
                return plan
            return None

        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    def _compare_plan_to_execution(
        self,
        plan_span: CanonicalSpan,
        plan_data: dict[str, Any],
        exec_span: CanonicalSpan,
        trace: CanonicalTrace,
    ) -> list[FailureEvidence]:
        """Compare plan intent against actual execution results."""
        evidence: list[FailureEvidence] = []

        planned_tools = set(plan_data.get("tools_to_use", []))
        planned_facts = plan_data.get("required_facts", [])

        # Get the actual tool calls made during execution by looking at
        # child generation spans under the execution span
        actual_tool_calls = self._extract_tool_calls_from_children(
            exec_span, trace
        )
        actual_results = self._extract_results(exec_span)

        # Check 1: Were completely different tools used than planned?
        if planned_tools and actual_tool_calls:
            used_tools = {tc.get("tool", "") for tc in actual_tool_calls}
            unexpected_tools = used_tools - planned_tools
            missing_tools = planned_tools - used_tools

            if unexpected_tools and missing_tools:
                evidence.append(
                    FailureEvidence(
                        description=(
                            f"Plan required tools {sorted(planned_tools)} but "
                            f"execution used {sorted(used_tools)} instead. "
                            f"Missing: {sorted(missing_tools)}, "
                            f"Unexpected: {sorted(unexpected_tools)}."
                        ),
                        span_ids=[plan_span.span_id, exec_span.span_id],
                        details={
                            "planned_tools": sorted(planned_tools),
                            "used_tools": sorted(used_tools),
                            "missing_tools": sorted(missing_tools),
                            "unexpected_tools": sorted(unexpected_tools),
                        },
                    )
                )

        # Check 2: Do the research results address the planned facts?
        if planned_facts and actual_results:
            addressed = self._check_facts_addressed(planned_facts, actual_results)
            unaddressed = [f for f, ok in zip(planned_facts, addressed) if not ok]
            if len(unaddressed) > len(planned_facts) * 0.5:
                evidence.append(
                    FailureEvidence(
                        description=(
                            f"Plan required {len(planned_facts)} facts but "
                            f"{len(unaddressed)} were not addressed in results."
                        ),
                        span_ids=[plan_span.span_id, exec_span.span_id],
                        details={
                            "planned_facts": planned_facts,
                            "unaddressed_facts": unaddressed,
                            "results_preview": [r[:100] for r in actual_results[:5]],
                        },
                    )
                )

        return evidence

    def _extract_tool_calls_from_children(
        self, exec_span: CanonicalSpan, trace: CanonicalTrace
    ) -> list[dict[str, Any]]:
        """Extract tool call info from generation spans under the execution span."""
        tool_calls: list[dict[str, Any]] = []
        for span in trace.spans:
            if span.parent_span_id != exec_span.span_id:
                continue
            if span.span_type != "generation":
                continue
            # The output of generation spans contains the LLM's tool choice
            output = span.output
            if isinstance(output, dict):
                content = output.get("content", "")
            elif isinstance(output, str):
                content = output
            else:
                continue

            try:
                parsed = json.loads(content) if isinstance(content, str) else content
                if isinstance(parsed, dict) and "tool" in parsed:
                    tool_calls.append(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

        return tool_calls

    def _extract_results(self, exec_span: CanonicalSpan) -> list[str]:
        """Extract research results from an execution span's output."""
        output = exec_span.output
        if not output:
            return []
        if isinstance(output, dict):
            results = output.get("research_results", [])
            if isinstance(results, list):
                return [str(r) for r in results]
        return []

    def _check_facts_addressed(
        self, planned_facts: list[str], results: list[str]
    ) -> list[bool]:
        """Check which planned facts are addressed in the results."""
        addressed = []
        results_lower = " ".join(r.lower() for r in results)
        for fact in planned_facts:
            # Extract key terms from the fact
            terms = [w.lower() for w in fact.split() if len(w) > 3]
            # A fact is "addressed" if at least half its key terms appear in results
            if terms:
                matches = sum(1 for t in terms if t in results_lower)
                addressed.append(matches >= len(terms) * 0.4)
            else:
                addressed.append(True)
        return addressed
