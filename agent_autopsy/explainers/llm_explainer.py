"""LLM-based explainer — optional narrative generation.

This explainer:
- Receives only structured failure evidence and the report
- Never inspects raw traces
- Never invents new failures
- Never contradicts deterministic results
- If it fails, the autopsy is still complete and correct
"""

import json
import logging
from typing import Optional

import httpx

from agent_autopsy.config import Settings
from agent_autopsy.core.models import AutopsyReport, AutopsyResult
from agent_autopsy.explainers.base import Explainer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert agent reliability engineer. You are given a structured autopsy report of an AI agent execution trace.

Your job is to:
1. Explain the detected failures in plain language
2. Explain WHY each failure matters for agent reliability
3. Suggest concrete architectural improvements

Rules:
- Do NOT invent new failures beyond what is provided
- Do NOT contradict the deterministic analysis
- Focus on actionable insights
- Be concise and technical
- Use markdown formatting"""


class LLMExplainer(Explainer):
    """LLM-based explanation generator using an OpenAI or Azure OpenAI API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = (settings.llm_base_url or "").rstrip("/")
        self._api_key = settings.llm_api_key or ""
        self._model = settings.llm_model
        self._timeout = settings.llm_timeout
        self._max_tokens = settings.llm_max_tokens
        # Check if this is Azure OpenAI (has 'openai.azure.com' in URL)
        self._is_azure = "openai.azure.com" in self._base_url.lower()
        # Get API version from settings if available
        self._api_version = getattr(settings, 'llm_api_version', '2024-08-01-preview')

    async def explain(
        self, result: AutopsyResult, report: AutopsyReport
    ) -> Optional[str]:
        """Generate an LLM narrative from the structured autopsy result."""
        if not self._base_url:
            logger.warning("LLM base URL not configured; skipping explanation")
            return None

        prompt = self._build_prompt(result, report)

        try:
            return await self._call_llm(prompt)
        except Exception:
            logger.exception("LLM explanation request failed")
            return None

    def _build_prompt(self, result: AutopsyResult, report: AutopsyReport) -> str:
        """Build the user prompt from structured data only."""
        failures_summary = []
        for f in result.primary_failures + result.secondary_failures:
            failures_summary.append({
                "type": f.failure_type,
                "title": f.title,
                "severity": f.severity.value,
                "confidence": f.confidence,
                "evidence_count": len(f.evidence),
                "evidence_descriptions": [e.description for e in f.evidence],
            })

        context = {
            "trace_id": result.trace_id,
            "provider": result.provider,
            "status": result.status.value,
            "overall_severity": result.overall_severity.value,
            "confidence": result.confidence,
            "total_spans_analyzed": result.total_spans_analyzed,
            "primary_failure_count": len(result.primary_failures),
            "secondary_failure_count": len(result.secondary_failures),
            "failures": failures_summary,
            "report_summary": report.summary,
            "root_cause_analysis": report.root_cause_analysis,
        }

        return (
            "Analyze the following agent autopsy result and provide a clear, "
            "actionable narrative explanation:\n\n"
            f"```json\n{json.dumps(context, indent=2)}\n```"
        )

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the OpenAI or Azure OpenAI LLM API."""
        if self._is_azure:
            # Azure OpenAI endpoint format: https://your-resource.openai.azure.com/openai/deployments/{model}/chat/completions?api-version={api_version}
            url = f"{self._base_url}/openai/deployments/{self._model}/chat/completions?api-version={self._api_version}"
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["api-key"] = self._api_key
        else:
            # Standard OpenAI endpoint
            url = f"{self._base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._max_tokens,
            "temperature": 0.3,
        }
        
        # Add model field only for non-Azure OpenAI
        if not self._is_azure:
            payload["model"] = self._model

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return None

        return choices[0].get("message", {}).get("content")


def create_explainer(settings: Settings) -> Optional[Explainer]:
    """Factory: create an LLM explainer if configured, else return None."""
    if not settings.is_llm_available:
        logger.info("LLM explanation disabled or not configured")
        return None
    
    # Check if using Azure OpenAI
    is_azure = "openai.azure.com" in (settings.llm_base_url or "").lower()
    if is_azure:
        logger.info("LLM explainer enabled with Azure OpenAI model: %s", settings.llm_model)
    else:
        logger.info("LLM explainer enabled with model: %s", settings.llm_model)
    
    return LLMExplainer(settings)
