"""API request/response schemas — strict validation, no business logic."""

from typing import Optional

from pydantic import BaseModel, Field

from agent_autopsy.core.models import (
    AutopsyReport,
    AutopsyResult,
    AutopsyStatus,
    DetectedFailure,
    Severity,
)


class AutopsyRequest(BaseModel):
    """Request body for the autopsy endpoint.

    Only two fields are allowed: provider and trace_id.
    No prompts, agent code, state schemas, or configuration.
    """

    provider: str = Field(
        description="Observability provider name (currently only 'langfuse' is supported)",
        examples=["langfuse"],
        pattern="^[a-zA-Z][a-zA-Z0-9_-]*$",
        min_length=1,
        max_length=50,
    )
    trace_id: str = Field(
        description="Trace ID from the observability provider. This is the unique identifier that identifies a specific execution trace in your observability platform.",
        min_length=1,
        max_length=255,
        examples=[
            "0189d5b8-7b7a-7b7a-8b7a-7b7a8b7a8b7a",
            "trace_2024_01_01_12_34_56_789",
            "agent-workflow-12345"
        ],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "langfuse",
                "trace_id": "0189d5b8-7b7a-7b7a-8b7a-7b7a8b7a8b7a"
            }
        }


class AutopsyResponseSchema(BaseModel):
    """Response body for the autopsy endpoint."""

    result: AutopsyResult = Field(description="Machine-readable autopsy result")
    report: AutopsyReport = Field(description="Human-readable autopsy report")
    llm_explanation: Optional[str] = Field(
        default=None,
        description="Optional LLM-generated narrative (never influences detection)",
    )
    enhanced_data: Optional[dict] = Field(
        default=None,
        description="Enhanced data for detailed visualization (tool calls, planner decisions, etc.)",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok")
    version: str
    llm_enabled: bool
    available_providers: list[str]


class ErrorResponse(BaseModel):
    """Standardized error response.

    All API errors follow this consistent format for easy error handling.
    """

    error: str = Field(
        description="Error type code for programmatic handling",
        examples=["provider_error", "validation_error", "internal_error"]
    )
    message: str = Field(
        description="Human-readable error message describing what went wrong",
        examples=[
            "Trace not found: 0189d5b8-7b7a-7b7a-8b7a-7b7a8b7a8b7a",
            "Invalid provider: unknown_provider",
            "Failed to connect to Langfuse server"
        ]
    )
    trace_id: Optional[str] = Field(
        default=None,
        description="Related trace ID if the error is associated with a specific trace"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error": "provider_error",
                "message": "Trace not found: 0189d5b8-7b7a-7b7a-8b7a-7b7a8b7a8b7a",
                "trace_id": "0189d5b8-7b7a-7b7a-8b7a-7b7a8b7a8b7a"
            }
        }
