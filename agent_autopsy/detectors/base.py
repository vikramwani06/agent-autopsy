"""Base detector interface. All failure detectors must implement this.

Each detector:
- Detects exactly ONE semantic failure pattern
- Operates only on the canonical trace model
- Produces structured evidence
- Assigns a confidence score and severity level
- Never calls external services or uses an LLM
- Never modifies trace data
- Never depends on provider-specific fields
"""

from abc import ABC, abstractmethod

from agent_autopsy.core.models import CanonicalTrace, DetectedFailure


class FailureDetector(ABC):
    """Abstract base for semantic failure detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique detector identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this detector finds."""
        ...

    @abstractmethod
    def detect(self, trace: CanonicalTrace) -> list[DetectedFailure]:
        """Run detection on a canonical trace.

        Args:
            trace: The normalized, provider-agnostic trace.

        Returns:
            A list of detected failures (empty if none found).
        """
        ...
