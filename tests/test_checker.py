from datetime import date
from decimal import Decimal

from app.dialog.answer import compose_answer
from app.dialog.checker import check_reply
from app.dialog.facts import CardFacts
from app.llm.schemas import Intent, LLMResult

FACTS = CardFacts(
    last4="5506", status="active", outstanding=Decimal("4250.75"),
    minimum_due=Decimal("212.54"), due_date=date(2026, 11, 25), is_overdue=False,
)
GOOD = "Your outstanding balance is AED 4,250.75. The minimum payment of AED 212.54 is due on 25 November."


def test_accepts_correct_reply():
    assert check_reply(GOOD, FACTS, Intent.BOTH).ok


def test_accepts_other_date_styles_and_card_digits():
    reply = "On your card ending 5506 you owe AED 4250.75; pay at least AED 212.54 by November 25th, 2026."
    assert check_reply(reply, FACTS, Intent.BOTH).ok


def test_draft_reply_always_passes():
    for intent in (Intent.CARD_BALANCE, Intent.DUE_DATE, Intent.BOTH):
        assert check_reply(FACTS.draft_reply(intent), FACTS, intent).ok


def test_rejects_wrong_amount():
    result = check_reply(GOOD.replace("4,250.75", "4,520.75"), FACTS, Intent.BOTH)
    assert not result.ok
    assert any("4,520.75" in e for e in result.errors)


def test_rejects_wrong_date():
    result = check_reply(GOOD.replace("25 November", "26 November"), FACTS, Intent.BOTH)
    assert not result.ok
    assert any("wrong date" in e for e in result.errors)


def test_rejects_invented_extra_number():
    result = check_reply(GOOD + " Your credit limit is AED 15,000.00.", FACTS, Intent.BOTH)
    assert not result.ok


def test_rejects_missing_fact():
    result = check_reply("Your outstanding balance is AED 4,250.75.", FACTS, Intent.BOTH)
    assert not result.ok
    assert "missing due date" in result.errors


def test_rejects_amount_in_words():
    reply = "You owe four thousand two hundred dirhams. The minimum payment of AED 212.54 is due on 25 November."
    assert not check_reply(reply, FACTS, Intent.DUE_DATE).ok


def test_overdue_and_blocked_must_be_mentioned():
    facts = CardFacts("1434", "blocked", Decimal("900.00"), Decimal("100.00"), date(2026, 10, 29), True)
    assert not check_reply("The minimum payment of AED 100.00 was due on 29 October.", facts, Intent.DUE_DATE).ok
    assert check_reply(facts.draft_reply(Intent.DUE_DATE), facts, Intent.DUE_DATE).ok


class LyingLLM:
    def phrase_answer(self, payload, language):
        return LLMResult("Your balance is AED 1,000.00, due on 1 December.", "liar", "v1", 5)


def test_wrong_llm_reply_is_replaced_by_template():
    answer = compose_answer(LyingLLM(), FACTS, Intent.BOTH, "en")
    assert answer.source == "template"
    assert answer.text == FACTS.draft_reply(Intent.BOTH)
    assert answer.checker_errors
