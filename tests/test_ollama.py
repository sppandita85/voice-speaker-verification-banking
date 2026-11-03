"""The Ollama provider, with HTTP mocked (no Ollama needed)."""
import json

import httpx
import pytest
from pydantic import ValidationError

from app.llm.ollama import OllamaLLM
from app.llm.schemas import Intent


def llm_returning(content: str, seen: list | None = None) -> OllamaLLM:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})

    client = httpx.Client(base_url="http://ollama", transport=httpx.MockTransport(handler))
    return OllamaLLM("http://ollama", "llama3.1:8b", "v1", client=client)


def test_valid_intent_json():
    seen = []
    result = llm_returning('{"intent": "BOTH", "confidence": 0.93}', seen).classify_intent("how much and when", "en")
    assert result.value.intent == Intent.BOTH
    assert result.prompt_version == "intent.en.v1" and result.model == "llama3.1:8b"
    assert seen[0]["format"]["properties"]["intent"]  # JSON schema sent to Ollama
    assert seen[0]["options"]["temperature"] == 0


def test_unknown_label_is_rejected():
    with pytest.raises(ValidationError):
        llm_returning('{"intent": "TRANSFER_MONEY"}').classify_intent("send money", "en")


def test_non_json_is_rejected():
    with pytest.raises(ValidationError):
        llm_returning("Sure! The intent is BOTH.").classify_intent("x", "en")


def test_reply_json():
    result = llm_returning('{"reply": " You owe AED 1.00. "}').phrase_answer({"draft": "x"}, "en")
    assert result.value == "You owe AED 1.00." and result.prompt_version == "reply.en.v1"
