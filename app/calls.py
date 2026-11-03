"""Runs a call: audio -> STT -> state machine -> TTS, and logs every turn (PII masked).

Call state is kept in memory (fine for a single-laptop demo); turns are stored in the database.
"""
import base64
import logging
import threading
import time
import uuid

from app.config import Settings
from app.dialog.flow import CallFlow, CallSession, Outcome, TurnResult
from app.logging_utils import REDACTED, mask_pii
from app.models import Call, Turn, utcnow
from app import repo
from app.providers import Providers
from app.speech.base import AudioClip
from app.speech.speakable import to_speech

log = logging.getLogger("calls")


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class CallNotFound(Exception):
    pass


class CallManager:
    def __init__(self, settings: Settings, session_factory, providers: Providers):
        self.cfg = settings
        self.Session = session_factory
        self.p = providers
        self.flow = CallFlow(settings, providers.voice, providers.llm)
        self.sessions: dict[str, CallSession] = {}
        self._turn_seq: dict[str, int] = {}
        self._lock = threading.Lock()  # one turn at a time: the models are not shared safely

    def start_call(self, customer_id: int | None) -> dict:
        started = time.perf_counter()
        call_id = str(uuid.uuid4())
        with self._lock, self.Session() as db:
            s, result = self.flow.start(db, call_id, customer_id)
            db.add(Call(id=call_id, customer_id=s.customer_id))
            db.commit()
            self.sessions[call_id] = s
            self._turn_seq[call_id] = 0
            audio, tts_ms = self._speak(result.reply, s.language)
            self._record(db, s, "start", "", result, None, None, tts_ms, _ms(started))
        return self._response(s, "", result, audio)

    def handle_turn(self, call_id: str, audio: bytes | None, text: str | None) -> dict:
        s = self.sessions.get(call_id)
        if s is None:
            raise CallNotFound(call_id)

        started = time.perf_counter()
        with self._lock, self.Session() as db:
            stt_ms = None
            if text:  # typed fallback
                transcript = text
                # Fake mode only: the typed text stands in for the voice sample, so the fake demo can pass voice ID.
                clip = AudioClip(text.encode()) if self.cfg.speech_provider == "fake" else None
            else:
                clip = AudioClip(audio or b"")
                t = time.perf_counter()
                transcript = self.p.stt.transcribe(clip, s.language) if audio else ""
                stt_ms = _ms(t)

            state_before = s.state.value
            result = self.flow.handle(db, s, transcript, clip)
            reply_audio, tts_ms = self._speak(result.reply, s.language)
            self._record(db, s, state_before, transcript, result, stt_ms, result.llm_ms, tts_ms, _ms(started))
        return self._response(s, transcript, result, reply_audio)

    # ---- helpers ------------------------------------------------------------

    def _speak(self, text: str, language: str) -> tuple[str | None, int]:
        t = time.perf_counter()
        try:
            wav = self.p.tts.synthesize(to_speech(text, language), language)
            return base64.b64encode(wav).decode(), _ms(t)
        except Exception as exc:  # the text reply still works without audio
            log.warning("TTS failed: %s", exc)
            return None, _ms(t)

    def _record(self, db, s: CallSession, state_before, transcript, result: TurnResult, stt_ms, llm_ms, tts_ms, total_ms):
        seq = self._turn_seq[s.call_id]
        self._turn_seq[s.call_id] = seq + 1
        masked = REDACTED if (result.sensitive_input and transcript) else mask_pii(transcript)
        db.add(Turn(
            call_id=s.call_id, seq=seq, state=state_before, transcript_masked=masked,
            intent=result.intent, voice_score=result.voice_score, verify_result=result.verify_result,
            reply_source=result.reply_source, llm_model=result.llm_model, prompt_version=result.prompt_version,
            bot_reply_masked=mask_pii(result.reply), stt_ms=stt_ms, llm_ms=llm_ms or None, tts_ms=tts_ms,
            latency_ms=total_ms,
        ))
        call = db.get(Call, s.call_id)
        call.customer_id = s.customer_id
        call.outcome = s.outcome
        call.handover_reason = s.handover_reason
        if s.outcome != Outcome.IN_PROGRESS and call.ended_at is None:
            call.ended_at = utcnow()
        db.commit()
        log.info(
            "call=%s seq=%d state=%s intent=%s score=%s verify=%s source=%s model=%s prompt=%s latency=%dms "
            "checker=%s text=%r",
            s.call_id[:8], seq, state_before, result.intent, result.voice_score, result.verify_result,
            result.reply_source, result.llm_model, result.prompt_version, total_ms,
            result.checker_errors or "ok", masked,
        )

    def _response(self, s: CallSession, transcript: str, result: TurnResult, audio_b64: str | None) -> dict:
        customer_label = None
        if s.verified:  # the UI only learns who the caller is once they are verified
            with self.Session() as db:
                customer_label = repo.get_customer(db, s.customer_id).full_name
        return {
            "call_id": s.call_id,
            "transcript": mask_pii(transcript) if result.sensitive_input else transcript,
            "reply": result.reply,
            "audio_b64": audio_b64,
            "state": s.state.value,
            "verified": s.verified,
            "voice_score": result.voice_score,
            "verify_result": result.verify_result,
            "intent": result.intent,
            "reply_source": result.reply_source,
            "outcome": s.outcome,
            "handover_reason": s.handover_reason,
            "customer": customer_label,
        }
