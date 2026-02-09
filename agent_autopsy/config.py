"""Central configuration module. All settings loaded from environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # Application
    app_name: str = Field(default="Agent Autopsy", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Langfuse
    langfuse_public_key: str = Field(description="Langfuse public API key")
    langfuse_secret_key: str = Field(description="Langfuse secret API key")
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse API base URL",
    )
    langfuse_timeout: float = Field(
        default=30.0, description="Langfuse API request timeout in seconds"
    )

    # LLM (optional, explanation-only)
    llm_enabled: bool = Field(
        default=False, description="Feature flag to enable LLM explanations"
    )
    llm_base_url: Optional[str] = Field(
        default=None, description="LLM API base URL (e.g. local Ollama)"
    )
    llm_api_key: Optional[str] = Field(default=None, description="LLM API key")
    llm_model: str = Field(
        default="llama3", description="LLM model name for explanations"
    )
    llm_timeout: float = Field(
        default=60.0, description="LLM API request timeout in seconds"
    )
    llm_max_tokens: int = Field(
        default=2048, description="Max tokens for LLM response"
    )
    llm_api_version: str = Field(
        default="2024-08-01-preview", description="API version for Azure OpenAI"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def validate_langfuse_config(self) -> "Settings":
        """Fail fast if Langfuse configuration is missing."""
        if not self.langfuse_public_key or not self.langfuse_secret_key:
            raise ValueError(
                "Langfuse configuration is required. "
                "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
            )
        return self

    @model_validator(mode="after")
    def validate_llm_config(self) -> "Settings":
        """Gracefully disable LLM if configuration is absent."""
        if self.llm_enabled and not self.llm_base_url:
            self.llm_enabled = False
        return self

    @property
    def is_llm_available(self) -> bool:
        """Check if LLM explanation is available and enabled."""
        return self.llm_enabled and self.llm_base_url is not None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
