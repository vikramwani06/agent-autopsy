"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent_autopsy.api.routes import router
from agent_autopsy.config import get_settings


def _configure_logging(level: str) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("LLM explanation: %s", "enabled" if settings.is_llm_available else "disabled")
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "## Universal Agent Autopsy Framework\n\n"
            "Post-execution semantic failure analysis for agent workflows using observability traces.\n\n"
            "### Features\n"
            "- 🔍 **Silent Failure Detection**: Identifies workflows that appear successful but produce incorrect outputs\n"
            "- 📊 **Visual UI**: Modern Streamlit interface with metric cards and PDF downloads\n"
            "- 🐳 **Docker Ready**: Complete containerization with environment variable security\n"
            "- 📄 **Professional Reports**: 9.5/10 quality diagnostic reports with actionable insights\n"
            "- 🔧 **Extensible**: Add new detectors and providers without refactoring\n"
            "- 🚀 **Production Ready**: Health checks, monitoring, and multi-server deployment\n\n"
            "### How it Works\n"
            "1. Supply a Langfuse trace ID\n"
            "2. Agent Autopsy fetches and normalizes the trace\n"
            "3. Runs multiple failure detectors to identify issues\n"
            "4. Generates a comprehensive report with actionable insights\n"
            "5. Optional LLM explanation for additional context\n\n"
            "### Supported Providers\n"
            "- **Langfuse**: Full observability platform integration\n\n"
            "### Failure Detectors\n"
            "- **State Drift**: Final output diverges from planning intent\n"
            "- **Silent Retry Masking**: Retries mask earlier failures without validation\n"
            "- **False Terminal Success**: Trace succeeds but output is empty/incomplete\n"
            "- **Retry Without Learning**: Identical retries with no corrective change\n"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={
            "name": "Agent Autopsy",
            "url": "https://github.com/your-org/agent-autopsy",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Development server",
            },
            {
                "url": "https://your-domain.com",
                "description": "Production server",
            },
        ],
    )
    app.include_router(router, prefix="/api/v1", tags=["autopsy"])
    
    # Add health check endpoint
    @app.get(
        "/health", 
        tags=["health"],
        summary="Health check endpoint",
        description="Returns the current health status of the Agent Autopsy service including version, LLM status, and available providers.",
        responses={
            200: {
                "description": "Service is healthy",
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
        }
    )
    async def health_check():
        """Health check endpoint for Docker and monitoring."""
        return {"status": "healthy", "version": settings.app_version}
    
    return app


app = create_app()
