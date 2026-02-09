"""Langfuse trace provider — fetches and normalizes Langfuse traces.

This provider:
- Fetches traces using the Langfuse REST API
- Converts Langfuse observations into canonical spans
- Preserves execution order and retry attempts
- Preserves span inputs and outputs
- Performs NO analysis or detection
- Contains NO business logic
"""

import base64
import logging
from typing import Any

import httpx

from agent_autopsy.config import Settings
from agent_autopsy.core.models import CanonicalSpan, CanonicalTrace
from agent_autopsy.providers.base import ProviderError, TraceProvider
from agent_autopsy.utils.time_helpers import parse_iso_timestamp

logger = logging.getLogger(__name__)


class LangfuseProvider(TraceProvider):
    """Langfuse observability provider."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.langfuse_base_url.rstrip("/")
        self._timeout = settings.langfuse_timeout
        # Langfuse uses Basic auth with public_key:secret_key
        credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}"
        self._auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()

    @property
    def name(self) -> str:
        return "langfuse"

    async def fetch_trace(self, trace_id: str) -> CanonicalTrace:
        """Fetch a Langfuse trace and normalize to canonical representation."""
        raw_trace = await self._fetch_raw_trace(trace_id)
        observations = await self._fetch_observations(trace_id)
        return self._normalize(trace_id, raw_trace, observations)

    # ------------------------------------------------------------------
    # Private: API calls
    # ------------------------------------------------------------------

    async def _fetch_raw_trace(self, trace_id: str) -> dict[str, Any]:
        """Fetch the trace object from Langfuse API."""
        url = f"{self._base_url}/api/public/traces/{trace_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url, headers={"Authorization": self._auth_header}
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ProviderError(self.name, f"Trace not found: {trace_id}", trace_id)
            raise ProviderError(
                self.name,
                f"HTTP {exc.response.status_code}: {exc.response.text}",
                trace_id,
            )
        except httpx.RequestError as exc:
            raise ProviderError(
                self.name, f"Request failed: {exc}", trace_id
            )

    async def _fetch_observations(self, trace_id: str) -> list[dict[str, Any]]:
        """Fetch all observations for a trace, handling pagination."""
        observations: list[dict[str, Any]] = []
        page = 1
        limit = 100

        while True:
            url = (
                f"{self._base_url}/api/public/observations"
                f"?traceId={trace_id}&page={page}&limit={limit}"
            )
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(
                        url, headers={"Authorization": self._auth_header}
                    )
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as exc:
                raise ProviderError(
                    self.name,
                    f"Failed to fetch observations: HTTP {exc.response.status_code}",
                    trace_id,
                )
            except httpx.RequestError as exc:
                raise ProviderError(
                    self.name, f"Request failed: {exc}", trace_id
                )

            batch = data.get("data", [])
            observations.extend(batch)

            # Langfuse pagination: stop when we get fewer than limit
            if len(batch) < limit:
                break
            page += 1

        logger.info(
            "Fetched %d observations for trace %s", len(observations), trace_id
        )
        return observations

    # ------------------------------------------------------------------
    # Private: Normalization (no business logic)
    # ------------------------------------------------------------------

    def _normalize(
        self,
        trace_id: str,
        raw_trace: dict[str, Any],
        observations: list[dict[str, Any]],
    ) -> CanonicalTrace:
        """Convert Langfuse trace + observations into a CanonicalTrace."""
        spans = self._normalize_observations(observations)
        spans = self._assign_retry_indices(spans)

        return CanonicalTrace(
            trace_id=trace_id,
            provider=self.name,
            name=raw_trace.get("name"),
            start_time=parse_iso_timestamp(raw_trace.get("timestamp")),
            end_time=parse_iso_timestamp(raw_trace.get("updatedAt")),
            input=raw_trace.get("input"),
            output=raw_trace.get("output"),
            metadata=raw_trace.get("metadata") or {},
            tags=raw_trace.get("tags") or [],
            spans=spans,
        )

    def _normalize_observations(
        self, observations: list[dict[str, Any]]
    ) -> list[CanonicalSpan]:
        """Convert Langfuse observations to canonical spans."""
        spans: list[CanonicalSpan] = []

        for obs in observations:
            span = CanonicalSpan(
                span_id=obs.get("id", ""),
                parent_span_id=obs.get("parentObservationId"),
                name=obs.get("name", "unknown"),
                span_type=obs.get("type", "SPAN").lower(),
                start_time=parse_iso_timestamp(obs.get("startTime"))
                or parse_iso_timestamp(obs.get("createdAt")),
                end_time=parse_iso_timestamp(obs.get("endTime")),
                input=obs.get("input"),
                output=obs.get("output"),
                error=obs.get("statusMessage")
                if obs.get("level") == "ERROR"
                else None,
                metadata=obs.get("metadata") or {},
                status_message=obs.get("statusMessage"),
                level=obs.get("level"),
                completion_start_time=parse_iso_timestamp(
                    obs.get("completionStartTime")
                ),
                model=obs.get("model"),
                usage=obs.get("usage"),
            )
            spans.append(span)

        # Sort by start_time for chronological order
        spans.sort(key=lambda s: s.start_time)
        return spans

    def _assign_retry_indices(
        self, spans: list[CanonicalSpan]
    ) -> list[CanonicalSpan]:
        """Assign retry_index to spans that share the same name and parent.

        Retry attempts are identified as spans with the same name under the
        same parent, ordered chronologically.
        """
        from collections import defaultdict

        groups: dict[tuple[str, str | None], list[CanonicalSpan]] = defaultdict(list)
        for span in spans:
            key = (span.name, span.parent_span_id)
            groups[key].append(span)

        for group in groups.values():
            if len(group) > 1:
                for idx, span in enumerate(group):
                    span.retry_index = idx

        return spans
