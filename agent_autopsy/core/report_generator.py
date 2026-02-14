"""Report generator — produces layered markdown autopsy reports.

Reports are rendered from versioned Jinja2 templates stored in
``agent_autopsy/core/templates/``. Separate templates exist for
passed and failed traces so they can be extended, updated, versioned,
and maintained independently.

Template files:
  - ``report_passed.md.j2``  — for traces that passed all checks
  - ``report_failed.md.j2``  — for traces where issues were detected

This module is responsible for:
  1. Extracting structured data from the trace and result objects.
  2. Building a context dict that the template can consume.
  3. Rendering the template and returning an ``AutopsyReport``.
"""

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent_autopsy.core.models import (
    AutopsyReport,
    AutopsyResult,
    AutopsyStatus,
    CanonicalTrace,
    CanonicalSpan,
    DetectedFailure,
    FailureEvidence,
    Severity,
)


# ---------------------------------------------------------------------------
# Template engine setup
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(disabled_extensions=("md.j2",)),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)

# Logger for this module
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Labels & mappings
# ---------------------------------------------------------------------------

_SEVERITY_LABELS = {
    Severity.CRITICAL: "Critical",
    Severity.HIGH: "High",
    Severity.MEDIUM: "Medium",
    Severity.LOW: "Low",
    Severity.INFO: "Informational",
}

_SEVERITY_IMPACT = {
    Severity.CRITICAL: "The workflow produced a fundamentally wrong or empty result. End-users would receive incorrect or no information.",
    Severity.HIGH: "The workflow completed but the output is unreliable. Key information is missing or wrong.",
    Severity.MEDIUM: "The workflow mostly succeeded but has quality gaps that could affect accuracy.",
    Severity.LOW: "A minor inconsistency was found that is unlikely to affect the end result.",
    Severity.INFO: "No issues detected.",
}

_FAILURE_TYPE_LABELS = {
    "state_drift": "Execution Deviated from the Plan",
    "silent_retry_masking": "Errors Were Silently Hidden by Retries",
    "false_terminal_success": "Reported Success but Produced No Output",
    "retry_without_learning": "Repeated the Same Failed Approach",
    "wrong_tool_usage": "Wrong Tool Selected for the Task",
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_report(result: AutopsyResult, trace: CanonicalTrace) -> AutopsyReport:
    """Generate a layered, multi-audience autopsy report from templates."""
    is_pass = result.status == AutopsyStatus.PASS

    if is_pass:
        rendered = _render_passed_report(result, trace)
    else:
        rendered = _render_failed_report(result, trace)

    return AutopsyReport(
        summary=rendered,
        primary_failure_explanation="",
        secondary_failure_explanations="",
        root_cause_analysis="",
        suggested_fixes="",
    )


# ---------------------------------------------------------------------------
# Passed report rendering
# ---------------------------------------------------------------------------


def _render_passed_report(result: AutopsyResult, trace: CanonicalTrace) -> str:
    """Build context and render the passed report template."""
    step_rows = _extract_workflow_steps(trace)
    plan_info = _extract_plan_info(trace)

    total_duration = ""
    if trace.start_time and trace.end_time:
        total_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
        total_duration = _format_duration(total_ms)

    ctx = {
        "workflow_name": trace.name or "",
        "trace_id": result.trace_id,
        "severity_label": _SEVERITY_LABELS.get(result.overall_severity, "Unknown"),
        "confidence": result.confidence,
        "total_spans": result.total_spans_analyzed,
        "user_input": _extract_user_input(trace),
        "steps": [{"name": n, "duration": d, "status": s} for n, d, s in step_rows],
        "total_duration": total_duration,
        "plan": plan_info,
        "output_summary": _extract_output_summary(trace),
        "provider": trace.provider,
        "tags": trace.tags,
        "start_time": trace.start_time.isoformat() if trace.start_time else "",
        "end_time": trace.end_time.isoformat() if trace.end_time else "",
        "spans": [
            {
                "span_id": s.span_id[:12] + "…",
                "name": s.name,
                "span_type": s.span_type,
                "duration": _format_duration(s.duration_ms) if s.duration_ms else "—",
            }
            for s in trace.spans
        ],
        # Additional context for extended template
        "execution_context": {
            "trace_id": result.trace_id,
            "duration": total_duration,
            "environment": trace.provider,
            "agent": trace.name or "LangGraph",
        },
        "outcome_summary": {
            "status": "Passed",
            "signal": "All checkpoints satisfied",
            "deviation": "None detected",
        },
        # New detailed context
        "user_question": _extract_user_input(trace),
        "tool_calls": _extract_tool_calls(trace),
        "planner_decision": _extract_planner_decision(trace),
        "execution_tree": _build_execution_tree(trace),
    }

    template = _jinja_env.get_template("report_passed.md.j2")
    return template.render(**ctx)


# ---------------------------------------------------------------------------
# Failed report rendering
# ---------------------------------------------------------------------------


def _render_failed_report(result: AutopsyResult, trace: CanonicalTrace) -> str:
    """Build context and render the failed report template."""
    total_failures = len(result.primary_failures) + len(result.secondary_failures)

    # Build consolidated issues
    issues = _build_issues_context(result.primary_failures)
    minor_issues = _build_issues_context(result.secondary_failures)

    # At-a-glance summary
    issues_at_glance = []
    for issue in issues:
        issues_at_glance.append({
            "number": issue["number"],
            "label": issue["friendly_type"],
            "severity": issue["severity_label"],
            "count_note": f" ({issue['occurrence_count']} occurrences)" if issue["occurrence_count"] > 1 else "",
        })

    # Root causes
    failure_types = {f.failure_type for f in result.primary_failures + result.secondary_failures}
    root_causes = _build_root_causes(failure_types)
    has_compound = len(failure_types) > 1

    # Recommended actions
    actions, observability_action = _build_actions(failure_types)

    # Extract additional context
    step_rows = _extract_workflow_steps(trace)
    plan_info = _extract_plan_info(trace)
    total_duration = ""
    if trace.start_time and trace.end_time:
        total_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
        total_duration = _format_duration(total_ms)
    
    # Extract comprehensive trace-specific insights with error handling
    try:
        trace_insights = _extract_trace_insights(trace, result)
    except Exception as e:
        logger.warning(f"Error extracting trace insights: {e}")
        trace_insights = {}
    
    try:
        execution_analysis = _analyze_execution_flow(trace, result)
    except Exception as e:
        logger.warning(f"Error analyzing execution flow: {e}")
        execution_analysis = {}
    
    try:
        failure_context = _build_failure_context(result, trace)
    except Exception as e:
        logger.warning(f"Error building failure context: {e}")
        failure_context = {}

    ctx = {
        "workflow_name": trace.name or "",
        "trace_id": result.trace_id,
        "severity_label": _SEVERITY_LABELS.get(result.overall_severity, "Unknown"),
        "confidence": result.confidence,
        "total_spans": result.total_spans_analyzed,
        "total_failures": total_failures,
        "business_impact": _SEVERITY_IMPACT.get(result.overall_severity, ""),
        "issues_at_glance": issues_at_glance,
        "issues": issues,
        "minor_issues": minor_issues,
        "root_causes": root_causes,
        "has_compound_failure": has_compound,
        "compound_failure_text": (
            "Multiple failure types were detected in the same workflow, indicating "
            "systemic gaps in error handling, state management, and output validation. "
            "These issues likely share a common architectural root: the workflow "
            "stages operate in isolation without cross-stage validation."
        ),
        "recommended_actions": actions,
        "observability_action": observability_action,
        # Additional context for extended template
        "total_duration": total_duration,
        "provider": trace.provider,
        "tags": trace.tags,
        "user_input": _extract_user_input(trace),
        "plan": plan_info,
        "steps": [{"name": n, "duration": d, "status": s} for n, d, s in step_rows],
        # New detailed context
        "user_question": _extract_user_input(trace),
        "tool_calls": _extract_tool_calls(trace),
        "planner_decision": _extract_planner_decision(trace),
        "execution_tree": _build_execution_tree(trace),
        # Comprehensive trace-specific insights
        "trace_insights": trace_insights,
        "execution_analysis": execution_analysis,
        "failure_context": failure_context,
    }

    template = _jinja_env.get_template("report_failed.md.j2")
    return template.render(**ctx)


def _extract_user_input(trace: CanonicalTrace) -> str:
    """Extract the user's original query from the trace input."""
    inp = trace.input
    if not inp:
        return ""
    if isinstance(inp, str):
        return inp
    if isinstance(inp, dict):
        for key in ("query", "question", "input", "prompt", "message", "text"):
            if key in inp and isinstance(inp[key], str) and inp[key].strip():
                return inp[key].strip()
        # If there's a nested messages list (chat format)
        messages = inp.get("messages", [])
        if messages and isinstance(messages[-1], dict):
            return messages[-1].get("content", "")
    return str(inp)[:200]


def _extract_workflow_steps(trace: CanonicalTrace) -> list[tuple[str, str, str]]:
    """Extract workflow steps as (name, duration_str, status) tuples.

    Only includes meaningful workflow-level steps, not internal sub-spans.
    """
    if not trace.spans:
        return []

    # Use top-level spans (children of root) for the step overview.
    # If there's a single root span, use its children instead.
    root_spans = trace.root_spans
    if len(root_spans) == 1:
        steps = trace.children_of(root_spans[0].span_id)
        if not steps:
            steps = root_spans
    else:
        steps = root_spans

    rows: list[tuple[str, str, str]] = []
    for s in steps:
        dur = _format_duration(s.duration_ms) if s.duration_ms else "—"
        status = "Error" if s.has_error else "Completed"
        rows.append((s.name, dur, status))

    return rows


def _extract_plan_info(trace: CanonicalTrace) -> dict[str, Any]:
    """Extract plan details from a planner span's output."""
    for s in trace.spans:
        if "planner" not in s.name.lower():
            continue
        output = s.output
        if not output:
            continue
        if isinstance(output, dict):
            # Look for plan in the output directly or nested under a key
            plan = output.get("plan", output)
            if isinstance(plan, dict):
                return plan
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    return parsed.get("plan", parsed)
            except (json.JSONDecodeError, TypeError):
                pass
    return {}


def _extract_output_summary(trace: CanonicalTrace) -> str:
    """Extract a readable output summary from the trace."""
    output = trace.output
    if not output:
        return ""

    if isinstance(output, str):
        return output[:500] if len(output) > 500 else output

    if isinstance(output, dict):
        # Look for content fields
        for key in ("summary", "result", "answer", "response", "output", "text"):
            val = output.get(key)
            if isinstance(val, str) and val.strip():
                text = val.strip()
                return text[:500] if len(text) > 500 else text

        # Look for research results
        results = output.get("results", output.get("research_results", []))
        if isinstance(results, list) and results:
            lines = []
            for r in results[:10]:
                lines.append(f"- {r}" if isinstance(r, str) else f"- {str(r)[:150]}")
            return "\n".join(lines)

    return ""


def _extract_tool_calls(trace: CanonicalTrace) -> list[dict[str, Any]]:
    """Extract all tool calls from the trace with detailed information.

    Extraction strategy:
    1. TOOL span types (direct tool executions)
    2. tool_results arrays in chain span outputs
    3. Generation span tool_calls
    4. EVENT spans that represent tool calls
    """
    tool_calls: list[dict[str, Any]] = []

    # Identify root span IDs so we can skip their aggregated tool_results
    root_span_ids = {s.span_id for s in trace.root_spans}

    # Track seen (tool_name, span_id) pairs to deduplicate
    seen_keys: set[tuple[str, str]] = set()

    # --- Priority 1: TOOL span types (direct tool executions) ----------------
    for span in trace.spans:
        if span.span_type == "tool":
            tool_name = span.name or "Unknown"
            dedup_key = (tool_name, span.span_id)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Extract input and output
            tool_input = span.input if span.input else {}
            tool_output = span.output if span.output else {}
            
            # Determine status
            has_error = span.has_error or (span.level == "ERROR")
            status = "Error" if has_error else "Success"

            tool_calls.append({
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_output,
                "parent_step": span.parent_span_id or "root",
                "span_id": span.span_id[:12] + "…" if len(span.span_id) > 12 else span.span_id,
                "timestamp": span.start_time.isoformat() if span.start_time else None,
                "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
                "status": status,
                "error": span.error if span.error else None,
                "metadata": span.metadata,
            })

    # Track seen (tool_name, input) pairs for chain-based extraction
    seen_chain_keys: set[tuple[str, str]] = set()

    # --- Priority 2: tool_results in child chain span outputs ----------------
    for span in trace.spans:
        if span.span_type != "chain":
            continue
        if span.span_id in root_span_ids:
            continue  # skip root — it duplicates child data

        output = span.output
        if not isinstance(output, dict):
            continue

        results = output.get("tool_results", [])
        if not isinstance(results, list):
            continue

        for tr in results:
            if not isinstance(tr, dict):
                continue
            tool_name = tr.get("tool")
            if not tool_name:
                continue

            dedup_key = (tool_name, str(tr.get("input", "")))
            if dedup_key in seen_chain_keys:
                continue
            seen_chain_keys.add(dedup_key)

            tool_output = str(tr.get("output", ""))
            has_error = (
                "error" in tool_output.lower()
                or "not found" in tool_output.lower()
                or "not available" in tool_output.lower()
            )
            tool_calls.append({
                "tool_name": tool_name,
                "input": tr.get("input", ""),
                "output": tr.get("output", ""),
                "parent_step": span.name,
                "span_id": span.span_id[:12] + "…",
                "timestamp": span.start_time.isoformat() if span.start_time else None,
                "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
                "status": "Error" if has_error else "Success",
                # Preserve any analysis metadata attached to the tool result
                "relevant_to_query": tr.get("relevant_to_query"),
                "actual_relevance": tr.get("actual_relevance"),
                "misinterpretation": tr.get("misinterpretation"),
                "correct_interpretation": tr.get("correct_interpretation"),
                "relevance": tr.get("relevance"),
                "agent_belief": tr.get("agent_belief"),
                "reality": tr.get("reality"),
                "calculation": tr.get("calculation"),
                "misapplication": tr.get("misapplication"),
                "result": tr.get("result"),
                "basis": tr.get("basis"),
            })

    # --- Priority 3: generation span tool_calls -----------------------------
    for span in trace.spans:
        if span.span_type != "generation" or not span.output:
            continue
        calls = _extract_tool_calls_from_generation(span, span.output)
        for call in calls:
            tool_name = call.get("tool", "Unknown")
            dedup_key = (tool_name, span.span_id)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            
            tool_calls.append({
                "tool_name": tool_name,
                "input": call.get("input", {}),
                "output": call.get("output", ""),
                "parent_step": span.name,
                "span_id": span.span_id[:12] + "…" if len(span.span_id) > 12 else span.span_id,
                "timestamp": span.start_time.isoformat() if span.start_time else None,
                "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
                "status": "Error" if span.has_error else "Success",
            })

    # --- Priority 4: EVENT spans that might be tool calls -------------------
    for span in trace.spans:
        if span.span_type == "event" and span.name and "tool" in span.name.lower():
            tool_name = span.name
            dedup_key = (tool_name, span.span_id)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            
            tool_calls.append({
                "tool_name": tool_name,
                "input": span.input if span.input else {},
                "output": span.output if span.output else {},
                "parent_step": span.parent_span_id or "root",
                "span_id": span.span_id[:12] + "…" if len(span.span_id) > 12 else span.span_id,
                "timestamp": span.start_time.isoformat() if span.start_time else None,
                "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
                "status": "Error" if span.has_error else "Success",
            })

    return tool_calls


def _extract_tool_calls_from_generation(span: CanonicalSpan, output: Any) -> list[dict[str, Any]]:
    """Extract tool calls from a generation span's output."""
    tool_calls = []
    
    if isinstance(output, dict):
        content = output.get("content", "")
        tool_calls_info = output.get("tool_calls", [])
        
        # Handle tool_calls array if present
        if tool_calls_info and isinstance(tool_calls_info, list):
            for tc in tool_calls_info:
                if isinstance(tc, dict):
                    tool_calls.append({
                        "tool": tc.get("function", {}).get("name", "Unknown"),
                        "input": tc.get("function", {}).get("arguments", {})
                    })
        
        # Handle content string
        elif content:
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
                if isinstance(parsed, dict) and "tool" in parsed:
                    tool_calls.append(parsed)
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "tool" in item:
                            tool_calls.append(item)
            except (json.JSONDecodeError, TypeError):
                pass
    
    return tool_calls


def _extract_planner_decision(trace: CanonicalTrace) -> dict[str, Any]:
    """Extract detailed planner decision information.

    Extraction strategy:
    1. CHAIN spans named 'planner' or containing 'plan'
    2. GENERATION spans with planner-related content
    3. Spans with 'planning' or 'planner' in their name
    4. Analysis spans for additional context
    """
    root_span_ids = {s.span_id for s in trace.root_spans}

    planning_output: dict[str, Any] = {}
    planning_input: dict[str, Any] = {}
    analysis_data: dict[str, Any] = {}
    model_name = ""
    query = ""
    all_decisions: list[dict[str, Any]] = []

    for span in trace.spans:
        # --- CHAIN spans that might contain planning decisions ----------------
        if span.span_type == "chain" and ("planner" in span.name.lower() or "plan" in span.name.lower()):
            if isinstance(span.output, dict):
                planning_output.update(span.output)
            elif isinstance(span.output, str):
                try:
                    parsed = json.loads(span.output)
                    if isinstance(parsed, dict):
                        planning_output.update(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(span.input, dict):
                planning_input.update(span.input)
                # Extract query from input
                if not query:
                    for key in ("query", "question", "input", "prompt", "message", "text"):
                        val = span.input.get(key)
                        if isinstance(val, str) and val.strip():
                            query = val.strip()
                            break

        # --- GENERATION spans with planner content ----------------
        if span.span_type == "generation" and ("planner" in span.name.lower() or "plan" in span.name.lower()):
            if not model_name:
                model_name = span.model or ""
            
            # Extract from output
            if isinstance(span.output, dict):
                content = span.output.get("content", "")
                if content:
                    try:
                        parsed = json.loads(content) if isinstance(content, str) else content
                        if isinstance(parsed, dict):
                            planning_output.update(parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            # Extract from input
            if isinstance(span.input, dict) and not query:
                for key in ("query", "question", "input", "prompt", "message"):
                    val = span.input.get(key)
                    if isinstance(val, str) and val.strip():
                        query = val.strip()
                        break

        # --- planning span (exact name or substring match) ----------------
        if span.name.lower() in ("planning",) or "planner" in span.name.lower():
            if isinstance(span.output, dict):
                planning_output.update(span.output)
            elif isinstance(span.output, str):
                try:
                    parsed = json.loads(span.output)
                    if isinstance(parsed, dict):
                        planning_output.update(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
            if isinstance(span.input, dict):
                planning_input.update(span.input)

        # --- analysis span ------------------------------------------------
        if span.name == "analysis" and span.span_id not in root_span_ids:
            if isinstance(span.output, dict):
                analysis_data = span.output.get("analysis", span.output)

        # --- model name from any generation spans -----------------------------
        if span.span_type == "generation" and not model_name:
            model_name = span.model or span.name or ""

    # Resolve the input query if not already found
    if not query:
        query = planning_input.get("query", "")
    if not query:
        # Try from root span input
        for span in trace.root_spans:
            if isinstance(span.input, dict):
                for key in ("query", "question", "input", "prompt", "message"):
                    val = span.input.get(key)
                    if isinstance(val, str) and val.strip():
                        query = val.strip()
                        break
            elif isinstance(span.input, str):
                query = span.input
            if query:
                break
    if not query:
        # Try from trace-level input
        if isinstance(trace.input, dict):
            for key in ("query", "question", "input", "prompt", "message"):
                val = trace.input.get(key)
                if isinstance(val, str) and val.strip():
                    query = val.strip()
                    break
        elif isinstance(trace.input, str):
            query = trace.input
    if not query:
        query = _extract_user_input(trace)

    # Build plan from planning span output
    plan = planning_output.get("plan", {})
    if not isinstance(plan, dict):
        plan = {}
    decisions = planning_output.get("decisions", [])
    if not isinstance(decisions, list):
        decisions = []

    # Build reasoning summary from decisions
    reasoning_parts = []
    for d in decisions:
        if isinstance(d, dict):
            reasoning_parts.append(
                f"{d.get('decision', '')}: {d.get('reasoning', '')}"
            )
    reasoning_text = " → ".join(reasoning_parts) if reasoning_parts else ""

    return {
        "query": query,
        "plan_name": plan.get("plan_name", ""),
        "steps": plan.get("steps", []),
        "decision_branches": plan.get("decision_branches", []),
        "decisions": decisions,
        "execution_path": planning_output.get("execution_path", []),
        "status": planning_output.get("status", ""),
        "analysis": analysis_data,
        "model_name": model_name,
        "tools_needed": analysis_data.get("tools_needed", []),
        "category": analysis_data.get("category", ""),
        "domain": analysis_data.get("domain", ""),
        "key_requirements": analysis_data.get("key_requirements", []),
        "confidence": analysis_data.get("confidence", 0),
        "reasoning": reasoning_text,
    }


def _build_execution_tree(trace: CanonicalTrace) -> dict[str, Any]:
    """Build a hierarchical tree of execution for visualization."""
    # Create a mapping of span_id to span
    span_map = {s.span_id: s for s in trace.spans}
    
    # Build the tree structure
    tree = {
        "name": trace.name or "Root",
        "span_id": "root",
        "type": "trace",
        "duration": _format_duration(
            (trace.end_time - trace.start_time).total_seconds() * 1000
        ) if trace.start_time and trace.end_time else "—",
        "status": "Error" if any(s.has_error for s in trace.spans) else "Success",
        "children": []
    }
    
    # Helper to recursively build children
    def build_children(parent_id: str, parent_node: dict):
        for span in trace.spans:
            if span.parent_span_id == parent_id:
                child_node = {
                    "name": span.name,
                    "span_id": span.span_id[:12] + "…",
                    "type": span.span_type,
                    "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
                    "status": "Error" if span.has_error else "Success",
                    "children": []
                }
                parent_node["children"].append(child_node)
                # Recursively build children for this span
                build_children(span.span_id, child_node)
    
    # Start with root spans
    for root_span in trace.root_spans:
        root_node = {
            "name": root_span.name,
            "span_id": root_span.span_id[:12] + "…",
            "type": root_span.span_type,
            "duration": _format_duration(root_span.duration_ms) if root_span.duration_ms else "—",
            "status": "Error" if root_span.has_error else "Success",
            "children": []
        }
        tree["children"].append(root_node)
        build_children(root_span.span_id, root_node)
    
    return tree


def _format_duration(ms: float | None) -> str:
    """Format milliseconds into a human-readable duration."""
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _extract_trace_insights(trace: CanonicalTrace, result: AutopsyResult) -> dict[str, Any]:
    """Extract comprehensive trace-specific insights."""
    insights = {
        "total_chains": len([s for s in trace.spans if s.span_type == "chain"]),
        "total_generations": len([s for s in trace.spans if s.span_type == "generation"]),
        "total_tools": len([s for s in trace.spans if s.span_type == "tool"]),
        "error_count": len([s for s in trace.spans if s.has_error]),
        "error_spans": [],
        "longest_span": None,
        "shortest_span": None,
        "models_used": set(),
        "tools_used": set(),
        "retry_count": 0,
    }
    
    # Extract error spans
    for span in trace.spans:
        if span.has_error:
            insights["error_spans"].append({
                "name": span.name,
                "error": span.error,
                "span_type": span.span_type,
                "duration": _format_duration(span.duration_ms) if span.duration_ms else "—"
            })
        
        # Track models
        if span.model:
            insights["models_used"].add(span.model)
        
        # Track tools
        if span.span_type == "tool":
            insights["tools_used"].add(span.name)
        
        # Track retries
        if span.retry_index and span.retry_index > 0:
            insights["retry_count"] += 1
    
    # Find longest and shortest spans
    spans_with_duration = [s for s in trace.spans if s.duration_ms]
    if spans_with_duration:
        longest = max(spans_with_duration, key=lambda s: s.duration_ms)
        shortest = min(spans_with_duration, key=lambda s: s.duration_ms)
        insights["longest_span"] = {
            "name": longest.name,
            "duration": _format_duration(longest.duration_ms),
            "type": longest.span_type
        }
        insights["shortest_span"] = {
            "name": shortest.name,
            "duration": _format_duration(shortest.duration_ms),
            "type": shortest.span_type
        }
    
    insights["models_used"] = list(insights["models_used"])
    insights["tools_used"] = list(insights["tools_used"])
    
    return insights


def _analyze_execution_flow(trace: CanonicalTrace, result: AutopsyResult) -> dict[str, Any]:
    """Analyze the execution flow and identify key patterns."""
    analysis = {
        "execution_phases": [],
        "critical_path": [],
        "bottlenecks": [],
        "parallel_executions": 0,
        "sequential_chains": [],
    }
    
    # Identify execution phases (main chains)
    chain_spans = [s for s in trace.spans if s.span_type == "chain"]
    if chain_spans:
        try:
            chain_spans.sort(key=lambda s: s.start_time if s.start_time else "")
        except Exception as e:
            logger.warning(f"Error sorting chain spans: {e}")
    
    for chain in chain_spans:
        phase = {
            "name": chain.name,
            "duration": _format_duration(chain.duration_ms) if chain.duration_ms else "—",
            "status": "Error" if chain.has_error else "Success",
            "child_count": len([s for s in trace.spans if s.parent_span_id == chain.span_id]),
            "tools_called": len([s for s in trace.spans if s.parent_span_id == chain.span_id and s.span_type == "tool"]),
            "generations": len([s for s in trace.spans if s.parent_span_id == chain.span_id and s.span_type == "generation"])
        }
        analysis["execution_phases"].append(phase)
        analysis["sequential_chains"].append(chain.name)
    
    # Identify bottlenecks (spans taking >30% of total time)
    if trace.start_time and trace.end_time:
        try:
            total_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            if total_ms > 0:
                for span in trace.spans:
                    if span.duration_ms and span.duration_ms > (total_ms * 0.3):
                        analysis["bottlenecks"].append({
                            "name": span.name,
                            "duration": _format_duration(span.duration_ms),
                            "percentage": f"{(span.duration_ms / total_ms * 100):.1f}%",
                            "type": span.span_type
                        })
        except Exception as e:
            logger.warning(f"Error identifying bottlenecks: {e}")
    
    # Build critical path (longest chain of dependencies)
    root_spans = trace.root_spans
    for root in root_spans:
        path = _build_critical_path(root, trace.spans)
        if path:
            analysis["critical_path"].extend(path)
    
    return analysis


def _build_critical_path(span: CanonicalSpan, all_spans: list[CanonicalSpan]) -> list[dict[str, Any]]:
    """Build the critical path from a root span."""
    path = [{
        "name": span.name,
        "duration": _format_duration(span.duration_ms) if span.duration_ms else "—",
        "type": span.span_type
    }]
    
    # Find children and add longest child to path
    children = [s for s in all_spans if s.parent_span_id == span.span_id]
    if children:
        longest_child = max(children, key=lambda s: s.duration_ms if s.duration_ms else 0)
        path.extend(_build_critical_path(longest_child, all_spans))
    
    return path


def _build_failure_context(result: AutopsyResult, trace: CanonicalTrace) -> dict[str, Any]:
    """Build detailed context about the failures detected."""
    context = {
        "failure_summary": "",
        "affected_spans": [],
        "failure_timeline": [],
        "impact_analysis": "",
        "root_cause_hypothesis": "",
    }
    
    all_failures = result.primary_failures + result.secondary_failures
    
    if not all_failures:
        return context
    
    # Build failure summary
    failure_types = {f.failure_type for f in all_failures}
    if len(failure_types) == 1:
        failure_type = list(failure_types)[0]
        context["failure_summary"] = f"The trace exhibits {_FAILURE_TYPE_LABELS.get(failure_type, failure_type)}."
    else:
        failure_labels = []
        for ft in failure_types:
            label = _FAILURE_TYPE_LABELS.get(ft, ft)
            if label:
                failure_labels.append(label)
        if failure_labels:
            context["failure_summary"] = f"The trace exhibits multiple failure patterns: {', '.join(failure_labels)}."
        else:
            context["failure_summary"] = "Multiple failure patterns were detected."
    
    # Extract affected spans from evidence
    seen_spans = set()
    for failure in all_failures:
        for evidence in failure.evidence:
            for sid in evidence.span_ids:
                if sid not in seen_spans:
                    seen_spans.add(sid)
                    span = next((s for s in trace.spans if s.span_id == sid), None)
                    if span:
                        context["affected_spans"].append({
                            "name": span.name,
                            "type": span.span_type,
                            "failure_type": _FAILURE_TYPE_LABELS.get(failure.failure_type, failure.failure_type),
                            "description": evidence.description
                        })
    
    # Build failure timeline
    for failure in all_failures:
        for evidence in failure.evidence:
            for sid in evidence.span_ids:
                span = next((s for s in trace.spans if s.span_id == sid), None)
                if span and span.start_time:
                    context["failure_timeline"].append({
                        "timestamp": span.start_time.isoformat() if span.start_time else "Unknown",
                        "span": span.name,
                        "event": evidence.description
                    })
                    break  # one timeline entry per evidence is enough
    
    # Sort timeline by timestamp
    context["failure_timeline"].sort(key=lambda x: x["timestamp"])
    
    # Build impact analysis
    if result.overall_severity == Severity.CRITICAL:
        context["impact_analysis"] = "The failures detected have critical impact on the workflow output. The results cannot be trusted and may mislead end users."
    elif result.overall_severity == Severity.HIGH:
        context["impact_analysis"] = "The failures detected have significant impact on workflow reliability. Key information may be missing or incorrect."
    elif result.overall_severity == Severity.MEDIUM:
        context["impact_analysis"] = "The failures detected indicate quality issues that could affect accuracy in some scenarios."
    else:
        context["impact_analysis"] = "The failures detected are minor and unlikely to significantly impact the final output."
    
    # Build root cause hypothesis based on failure types
    if "wrong_tool_usage" in failure_types:
        context["root_cause_hypothesis"] = "The agent selected the wrong tool for the task, producing a semantically incorrect response. There is no validation gate to verify tool selection matches query intent."
    elif "state_drift" in failure_types:
        context["root_cause_hypothesis"] = "The workflow execution deviated from the planned approach, suggesting inadequate validation between planning and execution phases."
    elif "false_terminal_success" in failure_types:
        context["root_cause_hypothesis"] = "The workflow completed successfully despite producing no meaningful output, indicating missing output validation checks."
    elif "silent_retry_masking" in failure_types:
        context["root_cause_hypothesis"] = "Retry mechanisms masked underlying errors without proper error analysis or corrective action."
    elif "retry_without_learning" in failure_types:
        context["root_cause_hypothesis"] = "The workflow retried failed operations without modifying the approach, suggesting lack of adaptive error handling."
    else:
        context["root_cause_hypothesis"] = "Multiple failure patterns suggest systemic issues in error handling and validation."
    
    return context


# ===================================================================
# Context builders for failed report template
# ===================================================================


def _build_issues_context(failures: list[DetectedFailure]) -> list[dict[str, Any]]:
    """Build consolidated issue dicts for the template, grouped by failure type."""
    if not failures:
        return []

    grouped: dict[str, list[DetectedFailure]] = {}
    for f in failures:
        grouped.setdefault(f.failure_type, []).append(f)

    issues: list[dict[str, Any]] = []
    issue_num = 0

    for failure_type, group in grouped.items():
        issue_num += 1
        best_severity = max(group, key=lambda f: _severity_rank(f.severity)).severity
        best_confidence = max(f.confidence for f in group)

        # Deduplicated evidence blocks (rendered markdown)
        evidence_blocks: list[str] = []
        seen_formatted: set[str] = set()
        for failure in group:
            for ev in failure.evidence:
                friendly = _format_evidence_friendly(failure_type, ev)
                if not friendly or friendly in seen_formatted:
                    continue
                seen_formatted.add(friendly)
                evidence_blocks.append(friendly)

        issues.append({
            "number": issue_num,
            "friendly_type": _FAILURE_TYPE_LABELS.get(failure_type, failure_type),
            "severity_label": _SEVERITY_LABELS.get(best_severity, "Unknown"),
            "confidence": best_confidence,
            "occurrence_count": len(group),
            "narrative": _get_narrative(failure_type),
            "evidence_blocks": evidence_blocks,
            "tech_ref": _build_technical_reference_group(group),
        })

    return issues


def _severity_rank(severity: Severity) -> int:
    """Return a numeric rank for sorting (higher = more severe)."""
    return {Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2,
            Severity.HIGH: 3, Severity.CRITICAL: 4}.get(severity, 0)


# ---------------------------------------------------------------------------
# Narrative text per failure type
# ---------------------------------------------------------------------------

_NARRATIVES = {
    "state_drift": (
        "The workflow started by creating a research plan that clearly defined "
        "what information to gather and which tools to use. However, the execution "
        "step ignored this plan and worked on completely unrelated topics. "
        "The final output does not address the original request."
    ),
    "false_terminal_success": (
        "The workflow ran through all of its steps — planning, research, and "
        "summarization — and reported a successful completion. However, the "
        "final output is empty. The system returned a blank answer while "
        "claiming everything worked. This is a silent failure: no error was "
        "raised, so monitoring dashboards would show this as a success."
    ),
    "silent_retry_masking": (
        "A step in the workflow failed on its first attempt. The system "
        "automatically retried it, and the retry appeared to succeed. However, "
        "the original failure was silently discarded — no log, no alert, no "
        "validation. Data gathered before the failure may have been lost, and "
        "the final result could be based on incomplete information."
    ),
    "retry_without_learning": (
        "A step in the workflow failed and was retried multiple times. Each "
        "retry used the exact same input and received the exact same error. "
        "The system did not adapt its approach between attempts, wasting "
        "resources and producing no useful result."
    ),
    "wrong_tool_usage": (
        "The agent selected the wrong tool to answer the user's question. "
        "Instead of using the appropriate tool for the task, it chose an "
        "unrelated tool and then built a confident but completely incorrect "
        "answer on top of the irrelevant data. The workflow completed without "
        "errors, so monitoring systems would show this as a success — but the "
        "user received a semantically wrong response."
    ),
}


def _get_narrative(failure_type: str) -> str:
    return _NARRATIVES.get(failure_type, "")


# ---------------------------------------------------------------------------
# Evidence formatters (produce pre-rendered markdown strings)
# ---------------------------------------------------------------------------


def _format_evidence_friendly(failure_type: str, ev: FailureEvidence) -> str:
    details = ev.details or {}

    if failure_type == "state_drift":
        return _format_drift_evidence(ev, details)
    if failure_type == "false_terminal_success":
        return _format_empty_output_evidence(ev, details)
    if failure_type == "silent_retry_masking":
        return _format_retry_masking_evidence(ev, details)
    if failure_type == "retry_without_learning":
        return _format_retry_learning_evidence(ev, details)
    if failure_type == "wrong_tool_usage":
        return _format_wrong_tool_evidence(ev, details)

    return f"> {ev.description}"


def _format_drift_evidence(ev: FailureEvidence, details: dict[str, Any]) -> str:
    lines: list[str] = []

    planned_tools = details.get("planned_tools", [])
    used_tools = details.get("used_tools", [])
    missing_tools = details.get("missing_tools", [])
    unexpected_tools = details.get("unexpected_tools", [])

    if planned_tools and used_tools:
        lines.append("| | Details |")
        lines.append("|---|---|")
        lines.append(f"| **Expected tools** | {', '.join(planned_tools)} |")
        lines.append(f"| **Actual tools used** | {', '.join(used_tools)} |")
        if missing_tools:
            lines.append(f"| **Missing (should have been used)** | {', '.join(missing_tools)} |")
        if unexpected_tools:
            lines.append(f"| **Unexpected (should not have been used)** | {', '.join(unexpected_tools)} |")
        lines.append("")
        lines.append(
            "**Impact:** The AI used tools that have nothing to do with the original "
            "request. None of the planned lookups were performed."
        )
        return "\n".join(lines)

    planned_facts = details.get("planned_facts", [])
    unaddressed_facts = details.get("unaddressed_facts", [])
    results_preview = details.get("results_preview", [])

    if planned_facts and unaddressed_facts:
        lines.append("**What the user asked for:**")
        for fact in planned_facts:
            marker = "[ ]" if fact in unaddressed_facts else "[x]"
            lines.append(f"- {marker} {fact}")
        lines.append("")
        if results_preview:
            lines.append("**What the AI actually researched instead:**")
            for r in results_preview:
                lines.append(f"- {r}")
            lines.append("")
        lines.append(
            f"**Impact:** {len(unaddressed_facts)} out of {len(planned_facts)} "
            f"requested items were never looked up. The user's question was not answered."
        )
        return "\n".join(lines)

    return f"> {ev.description}"


def _format_empty_output_evidence(ev: FailureEvidence, details: dict[str, Any]) -> str:
    empty_fields = details.get("empty_content_fields", [])
    validation_count = details.get("validation_spans_found")
    lines: list[str] = []

    if empty_fields:
        field_names = ", ".join(f"`{f}`" for f in empty_fields)
        lines.append("| | Details |")
        lines.append("|---|---|")
        lines.append(f"| **Empty output fields** | {field_names} |")
        lines.append(f"| **Workflow status** | Reported as \"completed\" |")
        lines.append(f"| **Quality check present** | {'Yes' if validation_count else 'No'} |")
        lines.append("")
        lines.append(
            "**What this means:** The workflow executed every step without errors, "
            "but the final output is blank. From a user's perspective, they asked "
            "a question and received an empty response. From a monitoring perspective, "
            "this looks like a successful execution — making it especially dangerous "
            "because it won't trigger any alerts."
        )

    if validation_count is not None and validation_count == 0:
        lines.append("")
        lines.append(
            "**Why it wasn't caught:** The workflow has no quality gate that checks "
            "whether the output actually contains meaningful content before marking "
            "the task as complete."
        )

    return "\n".join(lines) if lines else f"> {ev.description}"


def _format_retry_masking_evidence(ev: FailureEvidence, details: dict[str, Any]) -> str:
    total = details.get("total_attempts")
    failed = details.get("failed_attempts")
    lines: list[str] = []

    if total and failed:
        lines.append("| | Details |")
        lines.append("|---|---|")
        lines.append(f"| **Total attempts** | {total} |")
        lines.append(f"| **Failed attempts** | {failed} |")
        lines.append(f"| **Post-retry validation** | None |")
        lines.append("")
        lines.append(
            "**What this means:** The system encountered a failure, retried, and "
            "moved on as if nothing happened. Any data from the failed attempt was "
            "silently discarded. The final result may be incomplete or inconsistent, "
            "but there is no way to tell from the output alone."
        )
        return "\n".join(lines)

    return f"> {ev.description}"


def _format_retry_learning_evidence(ev: FailureEvidence, details: dict[str, Any]) -> str:
    total = details.get("total_attempts")
    identical = details.get("identical_consecutive_pairs")
    lines: list[str] = []

    if total and identical:
        lines.append("| | Details |")
        lines.append("|---|---|")
        lines.append(f"| **Total attempts** | {total} |")
        lines.append(f"| **Identical consecutive attempts** | {identical} |")
        lines.append(f"| **Strategy adjusted between retries** | No |")
        lines.append("")
        lines.append(
            "**What this means:** The system tried the same thing multiple times "
            "expecting a different result. Each attempt used identical input and "
            "received identical output. This wastes compute resources and delays "
            "the response without making any progress toward a solution."
        )
        return "\n".join(lines)

    return f"> {ev.description}"


def _format_wrong_tool_evidence(ev: FailureEvidence, details: dict[str, Any]) -> str:
    tool_name = details.get("tool_name", "")
    actual_purpose = details.get("actual_purpose", "")
    tool_input = details.get("tool_input", "")
    tool_output = details.get("tool_output", "")
    lines: list[str] = []

    if tool_name:
        lines.append("| | Details |")
        lines.append("|---|---|")
        lines.append(f"| **Tool used** | `{tool_name}` |")
        if tool_input:
            lines.append(f"| **Input given** | {tool_input} |")
        if actual_purpose:
            lines.append(f"| **What should have been done** | {actual_purpose} |")
        lines.append(f"| **Correct usage** | No |")
        if tool_output and "error" in str(tool_output).lower():
            lines.append(f"| **Tool result** | Error (see below) |")
        lines.append("")
        lines.append(
            "**Impact:** The agent used a tool that has nothing to do with the "
            "user's actual question. The response is built on irrelevant data "
            "and is semantically incorrect, even though the workflow completed "
            "without raising any errors."
        )
        return "\n".join(lines)

    # Fallback for wrong-behavior span evidence
    span_name = details.get("span_name", "")
    matched_keywords = details.get("matched_keywords", [])
    reasoning = details.get("reasoning", [])

    if span_name:
        lines.append(f"**Span:** `{span_name}` (indicates incorrect reasoning)")
        if reasoning:
            lines.append("")
            lines.append("**Reasoning trail:**")
            items = reasoning if isinstance(reasoning, list) else [str(reasoning)]
            for r in items[:5]:
                lines.append(f"- {r}")
        lines.append("")
        lines.append(
            "**Impact:** The workflow contains a step that explicitly performs "
            "incorrect inference, leading to a wrong final answer."
        )
        return "\n".join(lines)

    return f"> {ev.description}"


# ---------------------------------------------------------------------------
# Technical reference builder (pre-rendered for template)
# ---------------------------------------------------------------------------


def _build_technical_reference_group(group: list[DetectedFailure]) -> str:
    """Build a single consolidated technical reference for a group of same-type failures."""
    first = group[0]
    lines = [
        "<details>",
        "<summary>Technical Reference (for developers)</summary>",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Detector | `{first.detector_name}` |",
        f"| Failure type | `{first.failure_type}` |",
    ]

    severities = sorted({f.severity.value for f in group})
    lines.append(f"| Severity | {', '.join(f'`{s}`' for s in severities)} |")

    confidences = sorted({f.confidence for f in group})
    lines.append(f"| Confidence | {', '.join(str(c) for c in confidences)} |")

    if len(group) > 1:
        lines.append(f"| Occurrences | {len(group)} |")

    all_span_ids: list[str] = []
    for f in group:
        for ev in f.evidence:
            all_span_ids.extend(ev.span_ids)
    if all_span_ids:
        unique_ids = list(dict.fromkeys(all_span_ids))
        formatted = ", ".join(f"`{s}`" for s in unique_ids)
        lines.append(f"| Span IDs | {formatted} |")

    lines.append("")

    seen_details: set[str] = set()
    ev_num = 0
    for f in group:
        for ev in f.evidence:
            if not ev.details:
                continue
            detail_key = json.dumps(ev.details, sort_keys=True, default=str)
            if detail_key in seen_details:
                continue
            seen_details.add(detail_key)
            ev_num += 1
            lines.append(f"**Evidence {ev_num}:**")
            lines.append("```json")
            lines.append(json.dumps(ev.details, indent=2, default=str))
            lines.append("```")
            lines.append("")

    lines.append("</details>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Root cause & action builders (produce data for template)
# ---------------------------------------------------------------------------

_ROOT_CAUSES = {
    "state_drift": {
        "title": "Plan-Execution Disconnect",
        "description": (
            "The planner and executor stages of the workflow are not coupled. "
            "The planner produces a structured plan (objective, required facts, "
            "tools to use), but the executor does not reference or validate against "
            "this plan. There is no contract enforcement between these stages.\n\n"
            "In a well-designed multi-agent workflow, the executor should receive "
            "the plan as a binding input and validate each action against it. "
            "Currently, the executor operates independently, which allows it to "
            "drift to unrelated tasks without detection."
        ),
    },
    "silent_retry_masking": {
        "title": "Missing Post-Retry Validation",
        "description": (
            "The retry mechanism recovers from failures but does not validate "
            "the recovered state. When a step fails and is retried, any partial "
            "results from the failed attempt are silently discarded. The retry "
            "succeeds on its own terms but may produce output that is inconsistent "
            "with what was accumulated before the failure.\n\n"
            "This is a common pattern in agent systems where retry logic is "
            "implemented at the infrastructure level without domain-aware validation."
        ),
    },
    "false_terminal_success": {
        "title": "No Output Validation Gate",
        "description": (
            "The workflow lacks a final validation step that checks whether the "
            "output contains meaningful content. The summarizer step can return "
            "an empty string without raising an error, and the workflow accepts "
            "this as a successful completion.\n\n"
            "This creates a class of silent failures that are invisible to "
            "monitoring systems — the trace shows no errors, all steps completed, "
            "but the user receives no useful output."
        ),
    },
    "retry_without_learning": {
        "title": "Non-Adaptive Retry Strategy",
        "description": (
            "The retry mechanism re-executes failed steps with identical inputs. "
            "Without incorporating error context or adjusting the approach, "
            "subsequent attempts are guaranteed to produce the same failure. "
            "This indicates a naive retry implementation that does not distinguish "
            "between transient and deterministic failures."
        ),
    },
    "wrong_tool_usage": {
        "title": "Incorrect Tool Selection",
        "description": (
            "The agent's analysis step misidentified the user's intent and selected "
            "a tool that is semantically unrelated to the task. The workflow has no "
            "validation gate that checks whether the selected tool is appropriate for "
            "the query before executing it. As a result, the agent confidently produced "
            "a response based on irrelevant data.\n\n"
            "In a well-designed agent workflow, tool selection should be validated "
            "against the query intent. The system should verify that the tool's domain "
            "matches the question's domain before proceeding with execution."
        ),
    },
}

_ACTIONS = {
    "state_drift": {
        "title": "Enforce plan compliance during execution",
        "owner": "Development team",
        "description": (
            "Add a validation step between the planner and executor that compares "
            "the executor's actions against the plan. Specifically:"
        ),
        "action_items": [
            "After the researcher step, compare the tools actually used against `plan.tools_to_use`.",
            "Compare the topics researched against `plan.required_facts`.",
            "If the overlap is below a threshold (e.g., 50%), reject the result and either "
            "re-run the executor with the plan explicitly in context, or fail with a clear error.",
        ],
    },
    "silent_retry_masking": {
        "title": "Add post-retry state validation",
        "owner": "Development team",
        "description": (
            "After any retry succeeds, validate that the recovered result is "
            "consistent with the workflow's accumulated state:"
        ),
        "action_items": [
            "Compare the retried output against what was expected from the plan.",
            "Log the original failure alongside the retry result for audit purposes.",
            "If the retried result is missing data that the failed attempt partially gathered, flag it.",
        ],
    },
    "false_terminal_success": {
        "title": "Add an output quality gate",
        "owner": "Development team",
        "description": (
            "Before the workflow reports completion, validate that the output "
            "contains meaningful content:"
        ),
        "action_items": [
            "Check that key output fields (e.g., `summary`, `result`) are non-empty.",
            "If the output is empty or below a minimum length, raise an explicit error "
            "instead of returning a blank response.",
            "Consider adding a confidence score to the output so downstream systems "
            "can decide whether to use it.",
        ],
    },
    "retry_without_learning": {
        "title": "Implement adaptive retry logic",
        "owner": "Development team / Platform team",
        "description": (
            "Replace the current retry mechanism with one that adapts between attempts:"
        ),
        "action_items": [
            "Pass the error message from the failed attempt as context to the retry.",
            "Try alternative tools or reformulated inputs on subsequent attempts.",
            "Set a maximum retry count and fail explicitly if all attempts produce identical results.",
        ],
    },
    "wrong_tool_usage": {
        "title": "Add tool selection validation",
        "owner": "Development team",
        "description": (
            "Validate that the selected tool is appropriate for the user's query "
            "before executing it:"
        ),
        "action_items": [
            "After the analysis step, verify the selected tool's domain matches the query intent.",
            "Maintain a mapping of tool capabilities and match them against query categories.",
            "If the tool selection confidence is low or the domain mismatch is detected, "
            "fall back to a more general tool or ask for clarification.",
            "Add a post-execution check that validates the tool output is semantically "
            "relevant to the original question.",
        ],
    },
}


def _build_root_causes(failure_types: set[str]) -> list[dict[str, str]]:
    """Build root cause dicts for the template."""
    causes = []
    for ft in ["wrong_tool_usage", "state_drift", "silent_retry_masking", "false_terminal_success", "retry_without_learning"]:
        if ft in failure_types and ft in _ROOT_CAUSES:
            causes.append(_ROOT_CAUSES[ft])
    return causes


def _build_actions(failure_types: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build recommended action dicts for the template.

    Returns (numbered_actions, observability_action).
    """
    actions: list[dict[str, Any]] = []
    num = 1
    for ft in ["wrong_tool_usage", "state_drift", "silent_retry_masking", "false_terminal_success", "retry_without_learning"]:
        if ft in failure_types and ft in _ACTIONS:
            action = dict(_ACTIONS[ft])
            action["number"] = num
            actions.append(action)
            num += 1

    observability = {
        "number": num,
        "title": "Improve observability at workflow boundaries",
        "owner": "Development team / Platform team",
        "description": (
            "Add structured logging at each stage transition so that issues like "
            "these are easier to detect in future runs:"
        ),
        "action_items": [
            "Log the plan output and the executor's actual actions side by side.",
            "Log retry attempts with their inputs, outputs, and error messages.",
            "Log the final output content (or lack thereof) before marking the workflow complete.",
            "Consider adding automated alerts for empty outputs or high retry counts.",
        ],
    }

    return actions, observability
