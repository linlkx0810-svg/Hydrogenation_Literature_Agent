"""Optional OpenAI Responses API adapter for strict JSON scientific components.

This module contains no scientific extraction or verification logic. It only
transports an already-built request to a live model using Structured Outputs.
The extractor/verifier prompts and response schemas remain owned by their
frozen modules.

The adapter imports the OpenAI SDK lazily so the core package and CI can run
without an API dependency or API key. Tests inject a fake client and never make
network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any


ADAPTER_VERSION = "openai-responses-json-v1"


class OpenAIProviderError(RuntimeError):
    """Base class for controlled live-provider failures."""


class OpenAIProviderConfigError(OpenAIProviderError):
    """Raised when the live provider is not configured safely."""


class OpenAIProviderResponseError(OpenAIProviderError):
    """Raised when the API response does not contain usable structured text."""


@dataclass
class OpenAIResponsesJSONProvider:
    """Provider adapter compatible with extractor and verifier request objects.

    Any request object supplied here must expose ``system_prompt``,
    ``user_prompt`` and ``response_schema`` attributes. The response schema is
    sent to the Responses API as a strict JSON Schema Structured Output.

    ``client`` is injectable for deterministic tests. When omitted, the adapter
    lazily imports ``openai.OpenAI`` and reads the API key from ``api_key_env``.
    No key is ever accepted as a source-code default.
    """

    model_name: str
    reasoning_effort: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    api_key_env: str = "OPENAI_API_KEY"
    schema_name: str = "scientific_json"
    client: Any | None = field(default=None, repr=False)
    last_response_id: str | None = field(default=None, init=False)
    last_response_model: str | None = field(default=None, init=False)
    adapter_version: str = field(default=ADAPTER_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise OpenAIProviderConfigError("model_name must be a non-empty exact model ID")
        if self.temperature is not None and not isinstance(self.temperature, (int, float)):
            raise OpenAIProviderConfigError("temperature must be numeric or null")
        if self.top_p is not None and not isinstance(self.top_p, (int, float)):
            raise OpenAIProviderConfigError("top_p must be numeric or null")
        if self.client is None:
            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise OpenAIProviderConfigError(
                    f"Missing API key in environment variable {self.api_key_env}"
                )
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as exc:  # pragma: no cover - depends on optional SDK
                raise OpenAIProviderConfigError(
                    "OpenAI SDK is not installed; install it in the live benchmark environment"
                ) from exc
            self.client = OpenAI(api_key=api_key)

    def complete_json(self, request: Any) -> str:
        """Call Responses API with the frozen request and strict JSON Schema."""

        for attr in ("system_prompt", "user_prompt", "response_schema"):
            if not hasattr(request, attr):
                raise OpenAIProviderConfigError(
                    f"request is missing required attribute: {attr}"
                )

        response_schema = dict(request.response_schema)
        payload: dict[str, Any] = {
            "model": self.model_name,
            "instructions": request.system_prompt,
            "input": request.user_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": self.schema_name,
                    "schema": response_schema,
                    "strict": True,
                }
            },
        }

        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.temperature is not None:
            payload["temperature"] = float(self.temperature)
        if self.top_p is not None:
            payload["top_p"] = float(self.top_p)

        assert self.client is not None
        try:
            response = self.client.responses.create(**payload)
        except Exception as exc:  # pragma: no cover - real transport failures
            raise OpenAIProviderError(f"OpenAI Responses API call failed: {exc}") from exc

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise OpenAIProviderResponseError(
                "OpenAI response did not contain non-empty output_text"
            )

        response_id = getattr(response, "id", None)
        response_model = getattr(response, "model", None)
        self.last_response_id = response_id if isinstance(response_id, str) else None
        self.last_response_model = response_model if isinstance(response_model, str) else None
        return output_text
