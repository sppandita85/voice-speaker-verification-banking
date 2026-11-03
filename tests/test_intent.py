import pytest

from app.llm import rules
from app.llm.fake import FakeLLM
from app.llm.schemas import Intent


@pytest.mark.parametrize(
    "text, expected",
    [
        ("How much do I owe on my credit card and when is it due?", Intent.BOTH),
        ("What's my outstanding balance?", Intent.CARD_BALANCE),
        ("When is my payment due?", Intent.DUE_DATE),
        ("What is the minimum I have to pay?", Intent.DUE_DATE),
        ("I want to talk to a real person", Intent.AGENT),
        ("Can I speak to an agent please", Intent.AGENT),
        ("Could you repeat that?", Intent.REPEAT),
        ("No thanks, that's all", Intent.GOODBYE),
        ("no", Intent.GOODBYE),
        ("I'd like to increase my credit limit", Intent.OTHER),
        ("Book me a flight to London", Intent.OTHER),
    ],
)
def test_rule_intents(text, expected):
    assert rules.classify(text) == expected


def test_fake_llm_returns_validated_intent():
    result = FakeLLM().classify_intent("how much do I owe", "en")
    assert result.value.intent == Intent.CARD_BALANCE
    assert result.model == "fake-rules"
