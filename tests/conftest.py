"""Shared fixtures: in-memory SQLite with the same synthetic data as the demo, and fake providers."""
from datetime import date

import pytest

from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.dialog.flow import CallFlow
from app.llm.fake import FakeLLM
from app.seed_data import seed
from app.speech.fakes import FakeVoiceID

TODAY = date(2026, 11, 3)


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        speech_provider="fake",
        llm_provider="fake",
        voice_accept_threshold=0.55,
        voice_stepup_threshold=0.40,
        max_verify_attempts=3,
    )


@pytest.fixture
def db(settings):
    engine = make_engine(settings.database_url)
    init_db(engine)
    Session = make_session_factory(engine)
    with Session() as session:
        seed(session, settings.mobile_hash_salt, today=TODAY, fake_voiceprints=True)
        yield session


@pytest.fixture
def voice(settings):
    return FakeVoiceID(score=0.8)


@pytest.fixture
def flow(settings, voice):
    return CallFlow(settings, voice, FakeLLM())
