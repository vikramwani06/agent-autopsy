"""Base provider interface. All observability providers must implement this."""

from abc import ABC, abstractmethod

from agent_autopsy.core.models import CanonicalTrace


class TraceProvider(ABC):
    """Abstract base for observability trace providers.

    Each provider fetches raw trace data from its platform and normalizes
    it into the canonical trace representation. Providers must NOT perform
    any analysis or detection logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'langfuse')."""
        ...

    @abstractmethod
    async def fetch_trace(self, trace_id: str) -> CanonicalTrace:
        """Fetch a trace by ID and return a canonical representation.

        Args:
            trace_id: The trace identifier in the provider's system.

        Returns:
            A fully normalized CanonicalTrace.

        Raises:
            ProviderError: If the trace cannot be fetched or parsed.
        """
        ...


class ProviderError(Exception):
    """Raised when a provider encounters an error fetching or normalizing a trace."""

    def __init__(self, provider: str, message: str, trace_id: str | None = None):
        self.provider = provider
        self.trace_id = trace_id
        super().__init__(f"[{provider}] {message}" + (f" (trace: {trace_id})" if trace_id else ""))
