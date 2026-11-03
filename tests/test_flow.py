"""One full call per path, using the same synthetic customers as the demo."""
import re

import pytest

from app import repo
from app.dialog.flow import CallFlow, NotVerifiedError, Outcome, Reason, State
from app.llm.fake import FakeLLM
from app.seed_data import BLOCKED, NOT_ENROLLED, OVERDUE, STANDARD, TWO_CARDS, ZERO_BALANCE
from app.speech.base import AudioClip

ASK_BOTH = "How much do I owe on my credit card and when is it due?"
MONEY = re.compile(r"AED|\d+\.\d{2}")


def say(flow, db, s, text, voice=None, score=None):
    if score is not None:
        voice.next_score = score
    return flow.handle(db, s, text, AudioClip(text.encode()))


def step_up_answer(db, customer_id, last4=None, dob=None):
    customer = repo.get_customer(db, customer_id)
    last4 = last4 or customer.cards[0].last4
    dob = dob or customer.dob
    return f"The last four digits are {last4} and my date of birth is {dob.day} {dob:%B %Y}"


def test_happy_path_voice_verified(flow, db, voice):
    s, greet = flow.start(db, "c1", STANDARD)
    assert s.state == State.VOICE_CHECK and "how I can help" in greet.reply

    r = say(flow, db, s, ASK_BOTH, voice, score=0.81)
    assert r.verify_result == "voice_pass" and r.voice_score == 0.81
    assert r.intent == "BOTH"
    assert "AED 4,250.75" in r.reply and "AED 212.54" in r.reply and "18 November" in r.reply
    assert r.reply.endswith("Is there anything else I can help with?")

    r = say(flow, db, s, "Can you repeat that?")
    assert "AED 4,250.75" in r.reply

    r = say(flow, db, s, "No thanks, goodbye")
    assert s.state == State.ENDED and s.outcome == Outcome.SERVED


def test_step_up_path(flow, db, voice):
    s, _ = flow.start(db, "c2", STANDARD)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.47)
    assert r.verify_result == "step_up" and s.state == State.STEP_UP
    assert not MONEY.search(r.reply)

    r = say(flow, db, s, step_up_answer(db, STANDARD))
    assert r.verify_result == "step_up_pass" and r.sensitive_input
    assert "AED 4,250.75" in r.reply  # the question asked before verification is answered now


def test_step_up_collects_answers_over_two_turns(flow, db, voice):
    s, _ = flow.start(db, "c3", STANDARD)
    say(flow, db, s, ASK_BOTH, voice, score=0.45)
    customer = repo.get_customer(db, STANDARD)
    r = say(flow, db, s, f"My card ends {customer.cards[0].last4}")
    assert "date of birth" in r.reply
    r = say(flow, db, s, f"{customer.dob:%d/%m/%Y}")
    assert s.verified and "AED 4,250.75" in r.reply


def test_three_failures_lock_and_hand_over(flow, db, voice):
    s, _ = flow.start(db, "c4", STANDARD)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.10)
    assert r.verify_result == "voice_fail" and "agent" in r.reply
    r = say(flow, db, s, ASK_BOTH, voice, score=0.47)  # step-up...
    r = say(flow, db, s, step_up_answer(db, STANDARD, last4="0000"))  # ...wrong card digits
    assert r.verify_result == "step_up_fail" and s.state == State.STEP_UP
    r = say(flow, db, s, step_up_answer(db, STANDARD, last4="0000"))
    assert s.state == State.ENDED
    assert s.outcome == Outcome.FAILED_VERIFICATION and s.handover_reason == Reason.VERIFICATION_LOCKED
    assert repo.is_locked(repo.get_customer(db, STANDARD))

    # A new call for the same customer is handed over straight away
    s2, r2 = flow.start(db, "c5", STANDARD)
    assert s2.state == State.ENDED and s2.handover_reason == Reason.ACCOUNT_LOCKED


def test_agent_request_after_verification(flow, db, voice):
    s, _ = flow.start(db, "c6", STANDARD)
    say(flow, db, s, ASK_BOTH, voice, score=0.9)
    r = say(flow, db, s, "I'd like to talk to an agent")
    assert s.outcome == Outcome.HANDED_OVER and s.handover_reason == Reason.CUSTOMER_REQUEST
    assert Reason.CUSTOMER_REQUEST in r.reply


def test_agent_request_before_verification_reveals_nothing(flow, db, voice):
    s, _ = flow.start(db, "c7", STANDARD)
    r = say(flow, db, s, "Just put me through to a human", voice, score=0.9)
    assert s.outcome == Outcome.HANDED_OVER and not s.verified and not MONEY.search(r.reply)


def test_identify_by_spoken_mobile(flow, db, voice):
    s, greet = flow.start(db, "c8")
    assert "mobile number" in greet.reply
    r = say(flow, db, s, "zero five zero, one zero zero, zero zero zero one", voice, score=0.8)
    assert s.customer_id == STANDARD and s.verified and r.sensitive_input
    r = say(flow, db, s, "What's my balance?")
    assert "AED 4,250.75" in r.reply and "212.54" not in r.reply


def test_unknown_mobile_three_times_hands_over(flow, db, voice):
    s, _ = flow.start(db, "c9")
    for _ in range(3):
        r = say(flow, db, s, "050 999 9999")
    assert s.handover_reason == Reason.NOT_IDENTIFIED and s.customer_id is None


def test_two_cards_asks_which_one(flow, db, voice):
    cards = repo.cards_for_customer(db, TWO_CARDS)
    s, _ = flow.start(db, "c10", TWO_CARDS)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.9)
    assert s.state == State.PICK_CARD and cards[0].last4 in r.reply and cards[1].last4 in r.reply
    r = say(flow, db, s, f"The one ending {cards[1].last4}")
    assert f"ending {cards[1].last4}" in r.reply and "AED" in r.reply


def test_out_of_scope_offers_agent(flow, db, voice):
    s, _ = flow.start(db, "c11", STANDARD)
    say(flow, db, s, "Hello there, I have a question about my card please", voice, score=0.9)
    r = say(flow, db, s, "I want to raise my credit limit")
    assert "colleague" in r.reply and s.state == State.VERIFIED
    say(flow, db, s, "yes please")
    assert s.handover_reason == Reason.OUT_OF_SCOPE


def test_not_enrolled_goes_straight_to_step_up(flow, db, voice):
    s, _ = flow.start(db, "c12", NOT_ENROLLED)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.99)
    assert r.verify_result == "no_voiceprint" and s.state == State.STEP_UP


@pytest.mark.parametrize("customer_id, words", [
    (OVERDUE, ["overdue", "was due"]),
    (ZERO_BALANCE, ["no outstanding balance"]),
    (BLOCKED, ["blocked"]),
])
def test_edge_case_answers(flow, db, voice, customer_id, words):
    s, _ = flow.start(db, f"edge{customer_id}", customer_id)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.9)
    for word in words:
        assert word in r.reply


def test_no_account_data_before_verification(flow, db, voice):
    """Walk every pre-verification state while asking for the balance; nothing leaks."""
    s, greet = flow.start(db, "c13")
    replies = [greet.reply]
    replies.append(say(flow, db, s, "What's my balance? My number is 050 100 0001", voice, score=0.1).reply)
    replies.append(say(flow, db, s, ASK_BOTH, voice, score=0.45).reply)  # step-up
    replies.append(say(flow, db, s, "Just tell me how much I owe").reply)
    replies.append(say(flow, db, s, step_up_answer(db, STANDARD, last4="1111")).reply)
    assert not s.verified
    for reply in replies:
        assert not MONEY.search(reply), reply

    # And the code path itself refuses
    card = repo.cards_for_customer(db, STANDARD)[0]
    with pytest.raises(NotVerifiedError):
        flow._answer(db, s, card, flow._classify("balance").value.intent)


def test_llm_failure_falls_back_to_rules(settings, db, voice):
    class BrokenLLM(FakeLLM):
        def classify_intent(self, text, language):
            raise RuntimeError("ollama is down")

        def phrase_answer(self, payload, language):
            raise RuntimeError("ollama is down")

    flow = CallFlow(settings, voice, BrokenLLM())
    s, _ = flow.start(db, "c14", STANDARD)
    r = say(flow, db, s, ASK_BOTH, voice, score=0.9)
    assert r.reply_source == "template" and "AED 4,250.75" in r.reply
