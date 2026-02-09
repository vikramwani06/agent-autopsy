"""Canonical trace representation and domain models.

All downstream logic (detectors, reports, explainers) relies ONLY on these
provider-agnostic models. No Langfuse-specific or provider-specific fields.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Canonical Trace Representation
# ---------------------------------------------------------------------------


class CanonicalSpan(BaseModel):
    """A single execution span in the canonical trace model."""

    span_id: str = Field(description="Unique identifier for this span")
    parent_span_id: Optional[str] = Field(
        default=None, description="Parent span ID for tree reconstruction"
    )
    name: str = Field(description="Human-readable span name")
    span_type: str = Field(
        description="Span type (e.g. generation, span, event)"
    )
    start_time: datetime = Field(description="Span start timestamp")
    end_time: Optional[datetime] = Field(
        default=None, description="Span end timestamp"
    )
    input: Optional[Any] = Field(default=None, description="Span input data")
    output: Optional[Any] = Field(default=None, description="Span output data")
    error: Optional[str] = Field(default=None, description="Error message if any")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata"
    )
    status_message: Optional[str] = Field(
        default=None, description="Status message from the provider"
    )
    level: Optional[str] = Field(
        default=None, description="Log level (e.g. ERROR, WARNING, DEFAULT)"
    )
    completion_start_time: Optional[datetime] = Field(
        default=None, description="Time when completion started (for generations)"
    )
    model: Optional[str] = Field(
        default=None, description="Model used (for generation spans)"
    )
    usage: Optional[dict[str, Any]] = Field(
        default=None, description="Token usage info (for generation spans)"
    )
    retry_index: int = Field(
        default=0, description="Retry attempt index (0 = first attempt)"
    )

    @property
    def duration_ms(self) -> Optional[float]:
        """Duration in milliseconds, if both timestamps are present."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @property
    def has_error(self) -> bool:
        """Whether this span has an error."""
        return self.error is not None or self.level == "ERROR"


class CanonicalTrace(BaseModel):
    """Provider-agnostic execution trace — the single source of truth for analysis."""

    trace_id: str = Field(description="Original trace ID from the provider")
    provider: str = Field(description="Observability provider name")
    name: Optional[str] = Field(default=None, description="Trace name")
    start_time: Optional[datetime] = Field(default=None, description="Trace start")
    end_time: Optional[datetime] = Field(default=None, description="Trace end")
    input: Optional[Any] = Field(default=None, description="Trace-level input")
    output: Optional[Any] = Field(default=None, description="Trace-level output")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Trace-level metadata"
    )
    tags: list[str] = Field(default_factory=list, description="Trace tags")
    spans: list[CanonicalSpan] = Field(
        default_factory=list, description="Ordered execution spans"
    )

    @property
    def root_spans(self) -> list[CanonicalSpan]:
        """Top-level spans with no parent."""
        return [s for s in self.spans if s.parent_span_id is None]

    @property
    def terminal_span(self) -> Optional[CanonicalSpan]:
        """Last span by end_time (or start_time if end_time is missing)."""
        if not self.spans:
            return None
        return max(
            self.spans,
            key=lambda s: s.end_time or s.start_time,
        )

    def children_of(self, span_id: str) -> list[CanonicalSpan]:
        """Get direct children of a span."""
        return [s for s in self.spans if s.parent_span_id == span_id]

    def spans_by_name(self, name: str) -> list[CanonicalSpan]:
        """Get all spans matching a name (useful for retry detection)."""
        return [s for s in self.spans if s.name == name]


# ---------------------------------------------------------------------------
# Failure Detection Models
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Failure severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FailureEvidence(BaseModel):
    """Structured evidence supporting a detected failure."""

    description: str = Field(description="What was observed")
    span_ids: list[str] = Field(
        default_factory=list, description="Relevant span IDs"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional structured evidence"
    )


class DetectedFailure(BaseModel):
    """A single detected semantic failure."""

    detector_name: str = Field(description="Name of the detector that found this")
    failure_type: str = Field(description="Category of failure")
    title: str = Field(description="Short human-readable title")
    severity: Severity = Field(description="Failure severity")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Detection confidence (0-1)"
    )
    evidence: list[FailureEvidence] = Field(
        default_factory=list, description="Supporting evidence"
    )
    explanation: Optional[str] = Field(
        default=None, description="Human-readable explanation"
    )


# ---------------------------------------------------------------------------
# Autopsy Result Models
# ---------------------------------------------------------------------------


class AutopsyStatus(str, Enum):
    """Overall autopsy pass/fail status."""

    PASS = "pass"
    FAIL = "fail"


class AutopsyResult(BaseModel):
    """Machine-readable autopsy result."""

    trace_id: str = Field(description="Analyzed trace ID")
    provider: str = Field(description="Observability provider used")
    status: AutopsyStatus = Field(description="Overall pass/fail")
    overall_severity: Severity = Field(description="Highest severity found")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Aggregated confidence score"
    )
    primary_failures: list[DetectedFailure] = Field(
        default_factory=list, description="Primary (highest severity) failures"
    )
    secondary_failures: list[DetectedFailure] = Field(
        default_factory=list, description="Lower severity failures"
    )
    total_spans_analyzed: int = Field(
        default=0, description="Number of spans analyzed"
    )
    detectors_run: list[str] = Field(
        default_factory=list, description="Names of detectors executed"
    )


class AutopsyReport(BaseModel):
    """Human-readable autopsy report — a first-class artifact."""

    summary: str = Field(description="Executive summary")
    primary_failure_explanation: str = Field(
        description="Detailed explanation of primary failures"
    )
    secondary_failure_explanations: str = Field(
        description="Explanation of secondary failures"
    )
    root_cause_analysis: str = Field(description="Root cause analysis")
    suggested_fixes: str = Field(description="Suggested architectural fixes")


class AutopsyResponse(BaseModel):
    """Final autopsy response combining machine-readable and human-readable output."""

    result: AutopsyResult = Field(description="Machine-readable autopsy result")
    report: AutopsyReport = Field(description="Human-readable autopsy report")
    llm_explanation: Optional[str] = Field(
        default=None,
        description="Optional LLM-generated narrative (never influences detection)",
    )
    enhanced_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Enhanced data for detailed visualization (tool calls, planner decisions, etc.)",
    )
