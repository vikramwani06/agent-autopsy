"""Provider registry — resolves provider name to implementation."""

import logging
from typing import Optional

from agent_autopsy.config import Settings
from agent_autopsy.providers.base import ProviderError, TraceProvider
from agent_autopsy.providers.langfuse_provider import LangfuseProvider

logger = logging.getLogger(__name__)

# Registry of available providers
_PROVIDER_FACTORIES: dict[str, type] = {
    "langfuse": LangfuseProvider,
}


def resolve_provider(provider_name: str, settings: Settings) -> TraceProvider:
    """Resolve a provider name to a configured TraceProvider instance.

    Args:
        provider_name: The provider identifier (e.g. 'langfuse').
        settings: Application settings.

    Returns:
        A configured TraceProvider instance.

    Raises:
        ProviderError: If the provider is not registered.
    """
    factory = _PROVIDER_FACTORIES.get(provider_name.lower())
    if factory is None:
        available = ", ".join(sorted(_PROVIDER_FACTORIES.keys()))
        raise ProviderError(
            provider_name,
            f"Unknown provider '{provider_name}'. Available: {available}",
        )
    logger.info("Resolved provider: %s", provider_name)
    return factory(settings)


def register_provider(name: str, provider_class: type) -> None:
    """Register a new provider class. Used for extensibility.

    Args:
        name: Provider identifier.
        provider_class: Class that implements TraceProvider.
    """
    _PROVIDER_FACTORIES[name.lower()] = provider_class
    logger.info("Registered provider: %s", name)


def available_providers() -> list[str]:
    """List all registered provider names."""
    return sorted(_PROVIDER_FACTORIES.keys())
