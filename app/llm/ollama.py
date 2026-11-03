"""Local LLM through Ollama's /api/chat. Output is forced to a JSON schema and validated by Pydantic.

Any error (Ollama down, timeout, invalid JSON) raises; the dialog then falls back to rules / the draft.
"""
import json
import time

import httpx
from pydantic import BaseModel

from app.llm.prompts import load_prompt
from app.llm.schemas import IntentResult, LLMResult, ReplyResult


class OllamaLLM:
    def __init__(self, url: str, model: str, prompt_version: str, client: httpx.Client | None = None):
        self.model_name = model
        self.prompt_version = prompt_version
        self.client = client or httpx.Client(base_url=url, timeout=60)

    def classify_intent(self, text: str, language: str) -> LLMResult:
        prompt = load_prompt("intent", language, self.prompt_version)
        value, ms = self._chat(prompt.text, text, IntentResult)
        return LLMResult(value, self.model_name, prompt.version_id, ms)

    def phrase_answer(self, payload: dict, language: str) -> LLMResult:
        prompt = load_prompt("reply", language, self.prompt_version)
        value, ms = self._chat(prompt.text, json.dumps(payload, ensure_ascii=False), ReplyResult)
        return LLMResult(value.reply.strip(), self.model_name, prompt.version_id, ms)

    def _chat(self, system: str, user: str, schema: type[BaseModel]) -> tuple[BaseModel, int]:
        started = time.perf_counter()
        response = self.client.post(
            "/api/chat",
            json={
                "model": self.model_name,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "format": schema.model_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
                "keep_alive": "30m",
            },
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        value = schema.model_validate_json(content)
        return value, int((time.perf_counter() - started) * 1000)
