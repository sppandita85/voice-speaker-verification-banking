"""Keyword rules for intent. Used by the fake LLM, as the fallback when Ollama fails,
and before verification (so mobile numbers and DOBs are never sent to the LLM)."""
import re

from app.llm.schemas import Intent

AGENT_WORDS = r"\b(agent|human|person|representative|operator|colleague|someone|customer service|real person)\b"
REPEAT_WORDS = r"\b(repeat|again|say that|pardon|didn'?t (catch|hear))\b"
GOODBYE_WORDS = r"\b(bye|goodbye|no thanks|no thank you|that'?s all|nothing else|that is all)\b|^\s*no\W*$"
BALANCE_WORDS = r"\b(balance|owe|outstanding|how much|total)\b"
DUE_WORDS = r"\b(due|when|date|deadline|minimum|pay by)\b"
YES_WORDS = r"\b(yes|yeah|yep|sure|please|okay|ok)\b"


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text.lower()) is not None


def wants_agent(text: str) -> bool:
    return _has(AGENT_WORDS, text)


def is_yes(text: str) -> bool:
    return _has(YES_WORDS, text) and not _has(r"\bno\b", text)


def classify(text: str) -> Intent:
    if wants_agent(text):
        return Intent.AGENT
    if _has(REPEAT_WORDS, text):
        return Intent.REPEAT
    if _has(GOODBYE_WORDS, text):
        return Intent.GOODBYE
    balance, due = _has(BALANCE_WORDS, text), _has(DUE_WORDS, text)
    if balance and due:
        return Intent.BOTH
    if balance:
        return Intent.CARD_BALANCE
    if due:
        return Intent.DUE_DATE
    return Intent.OTHER
