"""Autopsy Engine — central orchestration layer.

The engine coordinates:
1. Provider resolution
2. Trace fetching and normalization
3. Detector execution
4. Failure ranking and classification
5. Report generation

The engine does NOT contain:
- Detection logic
- Provider-specific logic
- LLM logic
"""

import logging
from typing import Optional

from agent_autopsy.config import Settings
from agent_autopsy.core.models import (
    AutopsyReport,
    AutopsyResponse,
    AutopsyResult,
    AutopsyStatus,
    CanonicalTrace,
    DetectedFailure,
    Severity,
)
from agent_autopsy.core.report_generator import generate_report, _extract_tool_calls, _extract_planner_decision, _build_execution_tree
from agent_autopsy.detectors.registry import run_all_detectors
from agent_autopsy.explainers.base import Explainer
from agent_autopsy.providers.registry import resolve_provider

logger = logging.getLogger(__name__)

# Severity ranking for comparison
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}

# Threshold: failures at or above this severity are "primary"
_PRIMARY_SEVERITY_THRESHOLD = Severity.HIGH


async def run_autopsy(
    provider_name: str,
    trace_id: str,
    settings: Settings,
    explainer: Optional[Explainer] = None,
) -> AutopsyResponse:
    """Execute a full autopsy on a trace.

    Args:
        provider_name: Observability provider identifier.
        trace_id: The trace ID to analyze.
        settings: Application settings.
        explainer: Optional LLM explainer (never influences detection).

    Returns:
        Complete AutopsyResponse with machine-readable result and human-readable report.
    """
    logger.info("Starting autopsy for trace %s via provider %s", trace_id, provider_name)

    # 1. Resolve provider
    provider = resolve_provider(provider_name, settings)

    # 2. Fetch and normalize trace
    trace = await provider.fetch_trace(trace_id)
    logger.info(
        "Fetched trace with %d spans from %s", len(trace.spans), provider_name
    )

    # 3. Run all detectors
    all_failures, detectors_run = run_all_detectors(trace)
    logger.info(
        "Ran %d detectors, found %d total failures",
        len(detectors_run),
        len(all_failures),
    )

    # 4. Classify failures
    primary, secondary = _classify_failures(all_failures)

    # 5. Compute aggregates
    overall_severity = _compute_overall_severity(all_failures)
    overall_confidence = _compute_overall_confidence(all_failures)
    status = AutopsyStatus.FAIL if all_failures else AutopsyStatus.PASS

    # 6. Build machine-readable result
    result = AutopsyResult(
        trace_id=trace_id,
        provider=provider_name,
        status=status,
        overall_severity=overall_severity,
        confidence=overall_confidence,
        primary_failures=primary,
        secondary_failures=secondary,
        total_spans_analyzed=len(trace.spans),
        detectors_run=detectors_run,
    )

    # 7. Generate human-readable report
    report = generate_report(result, trace)
    
    # 8. Extract enhanced data for visualization
    enhanced_data = {
        "tool_calls": _extract_tool_calls(trace),
        "planner_decision": _extract_planner_decision(trace),
        "execution_tree": _build_execution_tree(trace),
        "trace": {
            "spans": [
                {
                    "span_id": s.span_id,
                    "name": s.name,
                    "span_type": s.span_type,
                    "parent_span_id": s.parent_span_id,
                    "start_time": s.start_time.isoformat() if s.start_time else None,
                    "end_time": s.end_time.isoformat() if s.end_time else None,
                    "duration_ms": s.duration_ms,
                    "input": s.input,
                    "output": s.output,
                    "error": s.error,
                    "status_message": s.status_message,
                    "level": s.level
                }
                for s in trace.spans
            ]
        }
    }

    # 9. Optional LLM explanation (never influences detection)
    llm_explanation: Optional[str] = None
    if explainer and all_failures:
        try:
            llm_explanation = await explainer.explain(result, report)
        except Exception:
            logger.exception("LLM explanation failed; autopsy result is unaffected")

    logger.info("Autopsy complete: status=%s, severity=%s", status.value, overall_severity.value)

    return AutopsyResponse(
        result=result,
        report=report,
        llm_explanation=llm_explanation,
        enhanced_data=enhanced_data,
    )


def _classify_failures(
    failures: list[DetectedFailure],
) -> tuple[list[DetectedFailure], list[DetectedFailure]]:
    """Classify failures into primary (high severity) and secondary."""
    primary: list[DetectedFailure] = []
    secondary: list[DetectedFailure] = []

    for f in sorted(
        failures,
        key=lambda x: (_SEVERITY_RANK.get(x.severity, 0), x.confidence),
        reverse=True,
    ):
        if _SEVERITY_RANK.get(f.severity, 0) >= _SEVERITY_RANK[_PRIMARY_SEVERITY_THRESHOLD]:
            primary.append(f)
        else:
            secondary.append(f)

    return primary, secondary


def _compute_overall_severity(failures: list[DetectedFailure]) -> Severity:
    """Return the highest severity among all failures."""
    if not failures:
        return Severity.INFO
    return max(failures, key=lambda f: _SEVERITY_RANK.get(f.severity, 0)).severity


def _compute_overall_confidence(failures: list[DetectedFailure]) -> float:
    """Aggregate confidence across all failures.

    Uses the maximum confidence as the overall score, since any single
    high-confidence failure is sufficient to flag the trace.
    """
    if not failures:
        return 0.0
    return max(f.confidence for f in failures)
