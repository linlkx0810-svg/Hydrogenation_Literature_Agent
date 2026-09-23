from types import SimpleNamespace

import pytest

from modules.llm_extractor import build_request, validate_response
from modules.openai_responses_provider import (
    ADAPTER_VERSION,
    OpenAIProviderConfigError,
    OpenAIProviderResponseError,
    OpenAIResponsesJSONProvider,
)
# Ported from the old freeze branch, blob 92ad93f5d729be7a7a42d6142336b57c9b4faa6f.
# One test that exercised modules.verifier (verifier-v1) is removed here because
# verifier-v1 is DEFERRED_TO_V1_1 and is not part of the Agent v1.0 graph.
# See docs/LLM_EXTRACTOR_LINEAGE_V1_TO_V2.md.


class FakeResponses:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            output_text=self.output_text,
            id="resp-test-001",
            model=kwargs["model"],
        )


class FakeClient:
    def __init__(self, output_text: str):
        self.responses = FakeResponses(output_text)


def _all_null_extractor_json() -> str:
    return (
        '{"ee_percent":null,"yield_percent":null,"h2_pressure_bar":null,'
        '"temperature_c":null,"reaction_time_h":null,"solvent":null,'
        '"ligand":null,"substrate_class":null}'
    )


def test_adapter_uses_strict_json_schema_for_extractor_request():
    client = FakeClient(_all_null_extractor_json())
    provider = OpenAIResponsesJSONProvider(
        model_name="model-test-exact-id",
        reasoning_effort="medium",
        client=client,
    )
    request = build_request("Synthetic evidence with no extractable values.")

    raw = provider.complete_json(request)
    validated = validate_response(raw)

    assert all(value is None for value in validated.values())
    assert provider.adapter_version == ADAPTER_VERSION
    assert provider.last_response_id == "resp-test-001"
    assert provider.last_response_model == "model-test-exact-id"

    kwargs = client.responses.last_kwargs
    assert kwargs is not None
    assert kwargs["model"] == "model-test-exact-id"
    assert kwargs["instructions"] == request.system_prompt
    assert kwargs["input"] == request.user_prompt
    assert kwargs["reasoning"] == {"effort": "medium"}
    assert kwargs["text"]["format"]["type"] == "json_schema"
    assert kwargs["text"]["format"]["strict"] is True
    assert kwargs["text"]["format"]["schema"] == dict(request.response_schema)


def test_optional_sampling_settings_are_only_sent_when_explicitly_pinned():
    client = FakeClient(_all_null_extractor_json())
    provider = OpenAIResponsesJSONProvider(
        model_name="model-test-exact-id",
        temperature=0.0,
        top_p=1.0,
        client=client,
    )
    provider.complete_json(build_request("Synthetic evidence."))

    kwargs = client.responses.last_kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["top_p"] == 1.0
    assert "reasoning" not in kwargs


def test_missing_model_id_is_rejected():
    with pytest.raises(OpenAIProviderConfigError):
        OpenAIResponsesJSONProvider(model_name="", client=FakeClient("{}"))


def test_empty_output_text_is_rejected():
    provider = OpenAIResponsesJSONProvider(
        model_name="model-test-exact-id",
        client=FakeClient(""),
    )
    with pytest.raises(OpenAIProviderResponseError):
        provider.complete_json(build_request("Synthetic evidence."))
