"""Utilities for ordering and grouping spans within a trace."""

from collections import defaultdict

from agent_autopsy.core.models import CanonicalSpan, CanonicalTrace


def order_spans_chronologically(spans: list[CanonicalSpan]) -> list[CanonicalSpan]:
    """Sort spans by start_time ascending."""
    return sorted(spans, key=lambda s: s.start_time)


def group_spans_by_name(spans: list[CanonicalSpan]) -> dict[str, list[CanonicalSpan]]:
    """Group spans by their name. Useful for retry detection."""
    groups: dict[str, list[CanonicalSpan]] = defaultdict(list)
    for span in order_spans_chronologically(spans):
        groups[span.name].append(span)
    return dict(groups)


def group_spans_by_parent(
    spans: list[CanonicalSpan],
) -> dict[str | None, list[CanonicalSpan]]:
    """Group spans by parent_span_id."""
    groups: dict[str | None, list[CanonicalSpan]] = defaultdict(list)
    for span in spans:
        groups[span.parent_span_id].append(span)
    return dict(groups)


def find_retry_groups(trace: CanonicalTrace) -> dict[str, list[CanonicalSpan]]:
    """Find groups of spans that appear to be retries of the same operation.

    A retry group is a set of spans with the same name that share a parent,
    or spans with the same name appearing multiple times.
    """
    name_groups = group_spans_by_name(trace.spans)
    retry_groups: dict[str, list[CanonicalSpan]] = {}

    for name, spans in name_groups.items():
        if len(spans) > 1:
            retry_groups[name] = order_spans_chronologically(spans)

    return retry_groups


def find_planning_spans(trace: CanonicalTrace) -> list[CanonicalSpan]:
    """Identify spans that likely represent planning or intent-setting steps.

    Heuristic: spans whose name contains planning-related keywords and
    appear early in the trace.
    """
    planning_keywords = {
        "plan", "planning", "intent", "goal", "objective",
        "strategy", "decide", "decision", "route", "router",
        "orchestrat", "dispatch", "initial", "setup",
        "analysis", "analyz",
    }
    planning_spans = []
    for span in order_spans_chronologically(trace.spans):
        name_lower = span.name.lower()
        if any(kw in name_lower for kw in planning_keywords):
            planning_spans.append(span)
    return planning_spans


def find_terminal_spans(trace: CanonicalTrace) -> list[CanonicalSpan]:
    """Identify spans that likely represent terminal/final steps.

    Heuristic: spans whose name contains terminal-related keywords or
    the chronologically last spans.
    """
    terminal_keywords = {
        "final", "output", "result", "response", "complete",
        "finish", "end", "return", "answer", "summary",
        "conclude", "deliver",
    }
    terminal_spans = []
    for span in trace.spans:
        name_lower = span.name.lower()
        if any(kw in name_lower for kw in terminal_keywords):
            terminal_spans.append(span)

    if not terminal_spans and trace.terminal_span:
        terminal_spans = [trace.terminal_span]

    return terminal_spans


def find_validation_spans(trace: CanonicalTrace) -> list[CanonicalSpan]:
    """Identify spans that likely represent validation steps."""
    validation_keywords = {
        "valid", "check", "verify", "assert", "confirm",
        "test", "quality", "review", "audit", "inspect",
    }
    return [
        span
        for span in trace.spans
        if any(kw in span.name.lower() for kw in validation_keywords)
    ]
