"""Fake LLM: keyword intent rules and returns the draft reply unchanged. No model needed."""
from app.llm import rules
from app.llm.schemas import IntentResult, LLMResult


class FakeLLM:
    model_name = "fake-rules"

    def classify_intent(self, text: str, language: str) -> LLMResult:
        return LLMResult(IntentResult(intent=rules.classify(text)), self.model_name, "rules", 0)

    def phrase_answer(self, payload: dict, language: str) -> LLMResult:
        return LLMResult(payload["draft"], self.model_name, "rules", 0)
