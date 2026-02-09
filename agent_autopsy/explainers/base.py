"""Base explainer interface.

The explanation layer is strictly optional. Rules:
- Receives only structured failure evidence
- Never inspects raw traces
- Never invents new failures
- Never contradicts deterministic results
"""

from abc import ABC, abstractmethod
from typing import Optional

from agent_autopsy.core.models import AutopsyReport, AutopsyResult


class Explainer(ABC):
    """Abstract base for explanation generators."""

    @abstractmethod
    async def explain(
        self, result: AutopsyResult, report: AutopsyReport
    ) -> Optional[str]:
        """Generate an optional human-readable narrative explanation.

        Args:
            result: The deterministic autopsy result (read-only).
            report: The generated report (read-only).

        Returns:
            A narrative explanation string, or None if unavailable.
        """
        ...
