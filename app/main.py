"""FastAPI app: three pages and a small JSON API.

    uvicorn app.main:app
"""
import itertools
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, select

from app import repo
from app.calls import CallManager, CallNotFound
from app.config import Settings, get_settings
from app.db import init_db, make_engine, make_session_factory
from app.dialog.verification import average_embedding, cosine
from app.logging_utils import quiet_noisy_loggers, setup_logging
from app.models import Call, Turn, Voiceprint
from app.providers import Providers, build_providers
from app.speech.base import AudioClip

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("app")


class StartCall(BaseModel):
    customer_id: int | None = None


def create_app(settings: Settings | None = None, providers: Providers | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    Session = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        init_db(engine)
        started = time.perf_counter()
        p = providers or build_providers(settings)
        quiet_noisy_loggers()
        log.info("Providers ready in %.1fs (speech=%s, llm=%s)", time.perf_counter() - started,
                 settings.speech_provider, settings.llm_provider)
        app.state.calls = CallManager(settings, Session, p)
        app.state.providers = p
        if settings.llm_provider != "fake":  # load the LLM into memory so the first call is not slow
            threading.Thread(target=_warm_up, args=(p.llm, settings.language), daemon=True).start()
        yield

    app = FastAPI(title="Card Balance Voice Bot (demo)", lifespan=lifespan)
    app.state.session_factory = Session
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    # ---- pages --------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    def call_page():
        return FileResponse(STATIC / "call.html")

    @app.get("/enroll", include_in_schema=False)
    def enroll_page():
        return FileResponse(STATIC / "enroll.html")

    @app.get("/log", include_in_schema=False)
    def log_page():
        return FileResponse(STATIC / "log.html")

    # ---- API ----------------------------------------------------------------

    @app.get("/api/config")
    def config():
        return {
            "language": settings.language,
            "speech_provider": settings.speech_provider,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.ollama_model if settings.llm_provider != "fake" else "fake-rules",
            "accept_threshold": settings.voice_accept_threshold,
            "stepup_threshold": settings.voice_stepup_threshold,
            "min_seconds": settings.voice_min_seconds,
        }

    @app.get("/api/customers")
    def customers():
        with Session() as db:
            enrolled = {row for row in db.scalars(select(Voiceprint.customer_id))}
            return [
                {
                    "id": c.id, "name": c.full_name, "mobile_masked": c.mobile_masked, "scenario": c.demo_note,
                    "enrolled": c.id in enrolled, "locked": repo.is_locked(c),
                }
                for c in repo.list_customers(db)
            ]

    @app.post("/api/customers/{customer_id}/unlock")
    def unlock(customer_id: int):
        with Session() as db:
            if repo.get_customer(db, customer_id) is None:
                raise HTTPException(404, "unknown customer")
            repo.unlock_customer(db, customer_id)
        return {"ok": True}

    @app.post("/api/calls")
    def start_call(body: StartCall):
        try:
            return app.state.calls.start_call(body.customer_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc))

    @app.post("/api/calls/{call_id}/turn")
    async def turn(call_id: str, audio: UploadFile | None = File(None), text: str | None = Form(None)):
        raw = await audio.read() if audio else None
        if not raw and not text:
            raise HTTPException(400, "send audio or text")
        try:
            return app.state.calls.handle_turn(call_id, raw, text)
        except CallNotFound:
            raise HTTPException(404, "call not found (the server may have restarted)")

    @app.get("/api/calls")
    def list_calls(limit: int = 50):
        with Session() as db:
            counts = dict(db.execute(select(Turn.call_id, func.count()).group_by(Turn.call_id)).all())
            calls = db.scalars(select(Call).order_by(Call.started_at.desc()).limit(limit))
            return [
                {
                    "id": c.id, "customer_id": c.customer_id, "started_at": c.started_at.isoformat(),
                    "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                    "outcome": c.outcome, "handover_reason": c.handover_reason, "turns": counts.get(c.id, 0),
                }
                for c in calls
            ]

    @app.get("/api/calls/{call_id}")
    def get_call(call_id: str):
        with Session() as db:
            call = db.get(Call, call_id)
            if call is None:
                raise HTTPException(404, "call not found")
            return {
                "id": call.id, "customer_id": call.customer_id, "outcome": call.outcome,
                "handover_reason": call.handover_reason,
                "turns": [
                    {c: getattr(t, c) for c in (
                        "seq", "state", "transcript_masked", "intent", "voice_score", "verify_result",
                        "reply_source", "llm_model", "prompt_version", "bot_reply_masked",
                        "stt_ms", "llm_ms", "tts_ms", "latency_ms")}
                    for t in call.turns
                ],
            }

    @app.post("/api/enroll/{customer_id}")
    async def enroll(customer_id: int, samples: list[UploadFile] = File(...)):
        if len(samples) < 3:
            raise HTTPException(400, "record at least 3 samples")
        voice = app.state.providers.voice
        clips = [AudioClip(await f.read()) for f in samples]
        seconds = [voice.duration(c) for c in clips]
        if any(s is not None and s < settings.voice_min_seconds for s in seconds):
            raise HTTPException(400, f"each sample must be at least {settings.voice_min_seconds}s of speech")
        embeddings = [voice.embed(c) for c in clips]
        # How alike the samples are to each other: a quick quality check for the presenter
        pairs = [cosine(a, b) for a, b in itertools.combinations(embeddings, 2)]
        with Session() as db:
            if repo.get_customer(db, customer_id) is None:
                raise HTTPException(404, "unknown customer")
            repo.save_voiceprint(db, customer_id, average_embedding(embeddings), len(clips), voice.model_name)
        return {
            "customer_id": customer_id,
            "samples": len(clips),
            "seconds": [round(s, 1) if s is not None else None for s in seconds],
            "consistency": round(sum(pairs) / len(pairs), 3),
        }

    return app


def _warm_up(llm, language: str) -> None:
    try:
        llm.classify_intent("what is my balance", language)
        log.info("LLM warmed up")
    except Exception as exc:
        log.warning("LLM warm-up failed (is Ollama running?): %s", exc)


app = create_app()
