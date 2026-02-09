"""API routes — orchestration only, no business logic.

Routes handle:
- Request validation
- Dependency injection
- Error handling
- Response formatting
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from agent_autopsy.api.schemas import (
    AutopsyRequest,
    AutopsyResponseSchema,
    ErrorResponse,
    HealthResponse,
)
from agent_autopsy.config import Settings, get_settings
from agent_autopsy.core.engine import run_autopsy
from agent_autopsy.explainers.base import Explainer
from agent_autopsy.explainers.llm_explainer import create_explainer
from agent_autopsy.providers.base import ProviderError
from agent_autopsy.providers.registry import available_providers

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_explainer(settings: Settings = Depends(get_settings)) -> Optional[Explainer]:
    """Dependency: resolve the optional LLM explainer."""
    return create_explainer(settings)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/autopsy",
    response_model=AutopsyResponseSchema,
    responses={
        200: {
            "description": "Autopsy completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "result": {
                            "trace_id": "example-trace-123",
                            "provider": "langfuse",
                            "status": "fail",
                            "overall_severity": "high",
                            "confidence": 0.85,
                            "total_spans_analyzed": 15,
                            "primary_failures": [
                                {
                                    "failure_type": "state_drift",
                                    "title": "State Drift Detected",
                                    "severity": "high",
                                    "confidence": 0.85,
                                    "evidence": [
                                        {
                                            "span_id": "span-123",
                                            "description": "Output diverges from planning intent"
                                        }
                                    ]
                                }
                            ],
                            "secondary_failures": []
                        },
                        "report": {
                            "summary": "Analysis revealed state drift in the agent workflow...",
                            "root_cause_analysis": "The agent failed to maintain consistency...",
                            "recommendations": ["Implement validation checkpoints..."],
                            "failure_details": []
                        },
                        "llm_explanation": "The autopsy reveals a critical state drift...",
                        "enhanced_data": {
                            "trace": {"spans": []},
                            "tool_calls": [],
                            "planner_decisions": []
                        }
                    }
                }
            }
        },
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        404: {"model": ErrorResponse, "description": "Trace not found in provider"},
        502: {"model": ErrorResponse, "description": "Provider connection error"},
    },
    summary="Run an autopsy on an agent trace",
    description=(
        "## Execute a Comprehensive Autopsy\n\n"
        "This endpoint performs a complete post-execution analysis of an agent workflow trace.\n\n"
        "### Process\n"
        "1. **Fetch Trace**: Retrieves the trace from the specified observability provider\n"
        "2. **Normalize**: Converts provider-specific format to canonical representation\n"
        "3. **Detect Failures**: Runs all available failure detectors\n"
        "4. **Generate Report**: Creates human-readable analysis\n"
        "5. **Optional LLM Explanation**: Provides additional narrative context\n\n"
        "### Required Parameters\n"
        "- `provider`: Currently supports 'langfuse'\n"
        "- `trace_id`: The unique identifier from your observability provider\n\n"
        "### Response Includes\n"
        "- **Machine-readable result**: Structured failure data\n"
        "- **Human-readable report**: Markdown-formatted analysis\n"
        "- **LLM explanation**: Optional narrative (if enabled)\n"
        "- **Enhanced data**: Additional visualization data\n"
    ),
)
async def run_autopsy_endpoint(
    request: AutopsyRequest,
    settings: Settings = Depends(get_settings),
    explainer: Optional[Explainer] = Depends(get_explainer),
) -> AutopsyResponseSchema:
    """Execute a full autopsy on the given trace."""
    logger.info(
        "Autopsy request: provider=%s, trace_id=%s",
        request.provider,
        request.trace_id,
    )

    try:
        response = await run_autopsy(
            provider_name=request.provider,
            trace_id=request.trace_id,
            settings=settings,
            explainer=explainer,
        )
        return AutopsyResponseSchema(
            result=response.result,
            report=response.report,
            llm_explanation=response.llm_explanation,
            enhanced_data=response.enhanced_data,
        )
    except ProviderError as exc:
        logger.warning("Provider error: %s", exc)
        status_code = 404 if "not found" in str(exc).lower() else 502
        raise HTTPException(
            status_code=status_code,
            detail=ErrorResponse(
                error="provider_error",
                message=str(exc),
                trace_id=request.trace_id,
            ).model_dump(),
        )
    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="validation_error",
                message=str(exc),
                trace_id=request.trace_id,
            ).model_dump(),
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description=(
        "## Health Status Endpoint\n\n"
        "Returns the current operational status of the Agent Autopsy service.\n\n"
        "### Response Fields\n"
        "- `status`: Service health status ('ok' or 'error')\n"
        "- `version`: Current application version\n"
        "- `llm_enabled`: Whether LLM explanations are configured and available\n"
        "- `available_providers`: List of configured observability providers\n\n"
        "### Use Cases\n"
        "- **Load Balancers**: Check service availability\n"
        "- **Monitoring**: Track service health\n"
        "- **Docker Health Checks**: Container orchestration\n"
    ),
    responses={
        200: {
            "description": "Service is healthy and operational",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "version": "1.0.0",
                        "llm_enabled": True,
                        "available_providers": ["langfuse"]
                    }
                }
            }
        }
    },
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Return application health status."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        llm_enabled=settings.is_llm_available,
        available_providers=available_providers(),
    )
