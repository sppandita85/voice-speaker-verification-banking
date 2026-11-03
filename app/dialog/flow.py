"""The call state machine. Each customer utterance is one turn; one method per state.

    IDENTIFY -> VOICE_CHECK -> (STEP_UP) -> VERIFIED <-> PICK_CARD -> ENDED

Rule: account data is only read in `_answer`, which refuses to run unless the call is verified.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from sqlalchemy.orm import Session

from app import repo
from app.config import Settings
from app.dialog.answer import compose_answer
from app.dialog.facts import CardFacts
from app.dialog.messages import msg
from app.dialog.parsing import parse_card_choice, parse_mobile, parse_step_up
from app.dialog.verification import VoiceDecision, decide
from app.identity import hash_mobile
from app.llm import rules
from app.llm.schemas import ANSWERABLE, Intent, IntentResult, LLMResult
from app.models import Card
from app.speech.base import AudioClip

log = logging.getLogger(__name__)


class State(str, Enum):
    IDENTIFY = "identify"
    VOICE_CHECK = "voice_check"
    STEP_UP = "step_up"
    VERIFIED = "verified"
    PICK_CARD = "pick_card"
    ENDED = "ended"


class Outcome:
    IN_PROGRESS = "in_progress"
    SERVED = "served"
    HANDED_OVER = "handed_over"
    FAILED_VERIFICATION = "failed_verification"
    ENDED = "ended"  # goodbye before any answer


class Reason:
    """Handover reason codes passed to the (simulated) agent desktop."""

    CUSTOMER_REQUEST = "AGENT_REQUESTED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    VERIFICATION_LOCKED = "VERIFY_FAILED_LOCKED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    NO_CARD_DATA = "NO_CARD_DATA"


LOCK_REASONS = {Reason.VERIFICATION_LOCKED, Reason.ACCOUNT_LOCKED}


class NotVerifiedError(Exception):
    pass


@dataclass
class CallSession:
    call_id: str
    language: str
    state: State = State.IDENTIFY
    customer_id: int | None = None
    verified: bool = False
    failed_attempts: int = 0
    identify_attempts: int = 0
    pending_intent: Intent | None = None  # asked before verification, answered after
    step_up_last4: str | None = None
    step_up_dob: date | None = None
    offered_agent: bool = False
    last_answer: str | None = None
    answered: bool = False
    outcome: str = Outcome.IN_PROGRESS
    handover_reason: str | None = None


@dataclass
class TurnResult:
    reply: str
    intent: str | None = None
    voice_score: float | None = None
    verify_result: str | None = None
    reply_source: str | None = None  # llm | template
    llm_model: str | None = None
    prompt_version: str | None = None
    llm_ms: int = 0
    sensitive_input: bool = False  # transcript holds mobile/DOB/card digits: never log it
    checker_errors: list[str] = field(default_factory=list)


class CallFlow:
    def __init__(self, settings: Settings, voice, llm):
        self.cfg = settings
        self.voice = voice
        self.llm = llm

    # ---- entry points -------------------------------------------------------

    def start(self, db: Session, call_id: str, customer_id: int | None = None) -> tuple[CallSession, TurnResult]:
        s = CallSession(call_id=call_id, language=self.cfg.language)
        if customer_id is None:
            return s, TurnResult(self._msg(s, "greet_identify"))

        customer = repo.get_customer(db, customer_id)
        if customer is None:
            raise ValueError(f"unknown customer {customer_id}")
        s.customer_id = customer.id
        if repo.is_locked(customer):
            return s, self._handover(s, Reason.ACCOUNT_LOCKED)
        s.state = State.VOICE_CHECK
        return s, TurnResult(self._msg(s, "greet_known"))

    def handle(self, db: Session, s: CallSession, transcript: str, clip: AudioClip | None) -> TurnResult:
        text = transcript.strip()
        if s.state == State.ENDED:
            return TurnResult(self._msg(s, "call_ended"))
        if not text:
            return TurnResult(self._msg(s, "didnt_catch"))
        handler = {
            State.IDENTIFY: self._identify,
            State.VOICE_CHECK: self._voice_check,
            State.STEP_UP: self._step_up,
            State.VERIFIED: self._request,
            State.PICK_CARD: self._pick_card,
        }[s.state]
        return handler(db, s, text, clip)

    # ---- states -------------------------------------------------------------

    def _identify(self, db, s, text, clip) -> TurnResult:
        if rules.wants_agent(text):
            return self._handover(s, Reason.CUSTOMER_REQUEST)

        mobile = parse_mobile(text)
        customer = repo.find_customer_by_mobile_hash(db, hash_mobile(mobile, self.cfg.mobile_hash_salt)) if mobile else None
        if customer is None:
            s.identify_attempts += 1
            if s.identify_attempts >= self.cfg.max_verify_attempts:
                result = self._handover(s, Reason.NOT_IDENTIFIED)
            else:
                result = TurnResult(self._msg(s, "mobile_not_found"))
            result.sensitive_input = True
            return result

        s.customer_id = customer.id
        if repo.is_locked(customer):
            result = self._handover(s, Reason.ACCOUNT_LOCKED)
        else:
            # The utterance with the mobile number is also the voice sample.
            s.state = State.VOICE_CHECK
            result = self._check_voice(db, s, clip)
        result.sensitive_input = True
        return result

    def _voice_check(self, db, s, text, clip) -> TurnResult:
        if rules.wants_agent(text):
            return self._handover(s, Reason.CUSTOMER_REQUEST)
        # Remember what they asked, but answer only after verification.
        classified = self._classify(text)
        intent = classified.value.intent
        s.pending_intent = intent if intent in ANSWERABLE else None
        result = self._check_voice(db, s, clip)
        self._attach_llm(result, classified, intent)
        return result

    def _step_up(self, db, s, text, clip) -> TurnResult:
        if rules.wants_agent(text):
            return self._handover(s, Reason.CUSTOMER_REQUEST)

        last4, dob = parse_step_up(text)
        s.step_up_last4 = last4 or s.step_up_last4
        s.step_up_dob = dob or s.step_up_dob
        if s.step_up_last4 is None and s.step_up_dob is None:
            result = TurnResult(self._msg(s, "step_up"))
        elif s.step_up_last4 is None:
            result = TurnResult(self._msg(s, "step_up_need_last4"))
        elif s.step_up_dob is None:
            result = TurnResult(self._msg(s, "step_up_need_dob"))
        else:
            customer = repo.get_customer(db, s.customer_id)
            card_last4s = {c.last4 for c in repo.cards_for_customer(db, s.customer_id)}
            matched = s.step_up_dob == customer.dob and s.step_up_last4 in card_last4s
            s.step_up_last4 = s.step_up_dob = None
            if matched:
                result = self._mark_verified(db, s, None, "step_up_pass")
            else:
                result = self._failed(db, s, "step_up_retry", None, "step_up_fail")
        result.sensitive_input = True
        return result

    def _request(self, db, s, text, clip) -> TurnResult:
        """Verified: work out what they want."""
        if s.offered_agent:
            s.offered_agent = False
            if rules.is_yes(text) or rules.wants_agent(text):
                return self._handover(s, Reason.OUT_OF_SCOPE)
            if re.match(r"\s*no\b", text.lower()):
                return TurnResult(f"{self._msg(s, 'no_transfer')} {self._msg(s, 'anything_else')}")

        classified = self._classify(text)
        intent = classified.value.intent
        if intent == Intent.AGENT:
            result = self._handover(s, Reason.CUSTOMER_REQUEST)
        elif intent == Intent.GOODBYE:
            s.state = State.ENDED
            s.outcome = Outcome.SERVED if s.answered else Outcome.ENDED
            result = TurnResult(self._msg(s, "goodbye"))
        elif intent == Intent.REPEAT:
            result = TurnResult(s.last_answer or self._msg(s, "nothing_to_repeat"))
        elif intent == Intent.OTHER:
            s.offered_agent = True
            result = TurnResult(self._msg(s, "out_of_scope"))
        else:
            result = self._answer_intent(db, s, intent)
        self._attach_llm(result, classified, intent)
        return result

    def _pick_card(self, db, s, text, clip) -> TurnResult:
        if rules.wants_agent(text):
            return self._handover(s, Reason.CUSTOMER_REQUEST)
        cards = repo.cards_for_customer(db, s.customer_id)
        choice = parse_card_choice(text, [c.last4 for c in cards])
        if choice is None:
            return TurnResult(self._msg(s, "pick_card_retry", example=cards[0].last4))
        intent, s.pending_intent = s.pending_intent or Intent.BOTH, None
        s.state = State.VERIFIED
        card = next(c for c in cards if c.last4 == choice)
        return self._answer(db, s, card, intent)

    # ---- verification helpers ----------------------------------------------

    def _check_voice(self, db, s, clip: AudioClip | None) -> TurnResult:
        voiceprint = repo.get_voiceprint(db, s.customer_id)
        if clip is None or voiceprint is None:
            s.state = State.STEP_UP
            return TurnResult(self._msg(s, "step_up"), verify_result="no_audio" if clip is None else "no_voiceprint")

        seconds = self.voice.duration(clip)
        if seconds is not None and seconds < self.cfg.voice_min_seconds:
            return TurnResult(self._msg(s, "too_short"), verify_result="too_short")

        score = round(self.voice.score(clip, voiceprint.embedding), 3)
        decision = decide(score, self.cfg.voice_accept_threshold, self.cfg.voice_stepup_threshold)
        if decision == VoiceDecision.PASS:
            return self._mark_verified(db, s, score, "voice_pass")
        if decision == VoiceDecision.STEP_UP:
            s.state = State.STEP_UP
            return TurnResult(self._msg(s, "step_up"), voice_score=score, verify_result="step_up")
        return self._failed(db, s, "voice_retry", score, "voice_fail")

    def _mark_verified(self, db, s, score, verify_result) -> TurnResult:
        s.verified = True
        s.state = State.VERIFIED
        pending, s.pending_intent = s.pending_intent, None
        if pending in ANSWERABLE:
            result = self._answer_intent(db, s, pending)
        else:
            result = TurnResult(self._msg(s, "verified_ask"))
        result.voice_score, result.verify_result = score, verify_result
        return result

    def _failed(self, db, s, retry_key, score, verify_result) -> TurnResult:
        s.failed_attempts += 1
        if s.failed_attempts >= self.cfg.max_verify_attempts:
            repo.lock_customer(db, s.customer_id, self.cfg.lock_minutes)
            result = self._handover(s, Reason.VERIFICATION_LOCKED)
        else:
            result = TurnResult(self._msg(s, retry_key))
        result.voice_score, result.verify_result = score, verify_result
        return result

    # ---- answering ----------------------------------------------------------

    def _answer_intent(self, db, s, intent: Intent) -> TurnResult:
        cards = repo.cards_for_customer(db, s.customer_id)
        if not cards:
            return self._handover(s, Reason.NO_CARD_DATA)
        if len(cards) > 1:
            s.state = State.PICK_CARD
            s.pending_intent = intent
            endings = f" {self._msg(s, 'and')} ".join(c.last4 for c in cards)
            return TurnResult(self._msg(s, "pick_card", count=len(cards), cards=endings), intent=intent.value)
        return self._answer(db, s, cards[0], intent)

    def _answer(self, db, s, card: Card, intent: Intent) -> TurnResult:
        if not s.verified:
            raise NotVerifiedError("account data requested before verification")
        statement = repo.latest_statement(db, card.id)
        if statement is None:
            return self._handover(s, Reason.NO_CARD_DATA)

        facts = CardFacts.from_db(card, statement)
        answer = compose_answer(self.llm, facts, intent, s.language)
        reply = f"{answer.text} {self._msg(s, 'anything_else')}"
        s.last_answer, s.answered = reply, True
        return TurnResult(
            reply,
            intent=intent.value,
            reply_source=answer.source,
            llm_model=answer.model,
            prompt_version=answer.prompt_version,
            llm_ms=answer.ms or 0,
            checker_errors=answer.checker_errors,
        )

    # ---- small helpers ------------------------------------------------------

    def _handover(self, s, reason: str) -> TurnResult:
        s.state = State.ENDED
        s.handover_reason = reason
        s.outcome = Outcome.FAILED_VERIFICATION if reason in LOCK_REASONS else Outcome.HANDED_OVER
        return TurnResult(self._msg(s, "locked" if reason in LOCK_REASONS else "handover", reason=reason))

    def _classify(self, text: str) -> LLMResult:
        try:
            return self.llm.classify_intent(text, self.cfg.language)
        except Exception as exc:  # LLM down or bad JSON: keyword rules still work
            log.warning("Intent LLM failed, using rules: %s", exc)
            return LLMResult(IntentResult(intent=rules.classify(text)), "fallback-rules", "rules", 0)

    @staticmethod
    def _attach_llm(result: TurnResult, classified: LLMResult, intent: Intent) -> None:
        result.intent = result.intent or intent.value
        result.llm_model = result.llm_model or classified.model
        result.prompt_version = result.prompt_version or classified.prompt_version
        result.llm_ms += classified.ms

    def _msg(self, s: CallSession, key: str, **kwargs) -> str:
        return msg(s.language, key, **kwargs)
