"""The HTTP API end to end, with fake providers and SQLite."""
import pytest
from fastapi.testclient import TestClient

from app.llm.fake import FakeLLM
from app.logging_utils import REDACTED, mask_pii
from app.main import create_app
from app.providers import Providers
from app.seed_data import NOT_ENROLLED, STANDARD, seed
from app.speech.fakes import FakeSTT, FakeTTS, FakeVoiceID
from tests.conftest import TODAY


@pytest.fixture
def voice():
    return FakeVoiceID(score=0.8)


@pytest.fixture
def client(settings, voice):
    app = create_app(settings, Providers(FakeSTT(), FakeTTS(), voice, FakeLLM()))
    with TestClient(app) as c:
        with app.state.session_factory() as db:
            seed(db, settings.mobile_hash_salt, today=TODAY, fake_voiceprints=True)
        yield c


def speak(client, call_id, words: str):
    return client.post(f"/api/calls/{call_id}/turn", files={"audio": ("a.webm", words.encode(), "audio/webm")}).json()


def test_full_call_over_http(client):
    start = client.post("/api/calls", json={"customer_id": STANDARD}).json()
    assert start["state"] == "voice_check" and start["audio_b64"] and start["customer"] is None

    r = speak(client, start["call_id"], "How much do I owe on my credit card and when is it due?")
    assert r["verified"] and r["voice_score"] == 0.8 and r["customer"] == "Aisha Al Mansoori"
    assert "AED 4,250.75" in r["reply"] and r["audio_b64"]

    r = client.post(f"/api/calls/{start['call_id']}/turn", data={"text": "no thanks, bye"}).json()
    assert r["outcome"] == "served"

    call = client.get(f"/api/calls/{start['call_id']}").json()
    assert call["outcome"] == "served" and len(call["turns"]) == 3
    answer = call["turns"][1]
    assert answer["intent"] == "BOTH" and answer["verify_result"] == "voice_pass"
    assert answer["prompt_version"] and answer["llm_model"] and answer["latency_ms"] >= 0

    listed = client.get("/api/calls").json()
    assert listed[0]["id"] == start["call_id"] and listed[0]["turns"] == 3


def test_identification_answers_are_never_logged(client):
    start = client.post("/api/calls", json={}).json()
    r = speak(client, start["call_id"], "my number is 050 100 0001")
    assert r["verified"] and "0001" not in r["transcript"]
    turns = client.get(f"/api/calls/{start['call_id']}").json()["turns"]
    assert turns[1]["transcript_masked"] == REDACTED


def test_failed_verification_locks_and_unlock_works(client, voice):
    start = client.post("/api/calls", json={"customer_id": STANDARD}).json()
    for _ in range(3):
        voice.next_score = 0.1
        r = speak(client, start["call_id"], "what's my balance please")
        assert "AED" not in r["reply"] and r["customer"] is None
    assert r["outcome"] == "failed_verification" and r["handover_reason"] == "VERIFY_FAILED_LOCKED"
    assert next(c for c in client.get("/api/customers").json() if c["id"] == STANDARD)["locked"]

    client.post(f"/api/customers/{STANDARD}/unlock")
    assert client.post("/api/calls", json={"customer_id": STANDARD}).json()["state"] == "voice_check"


def test_enrollment(client):
    assert not next(c for c in client.get("/api/customers").json() if c["id"] == NOT_ENROLLED)["enrolled"]
    files = [("samples", (f"s{i}.webm", f"sample {i}".encode(), "audio/webm")) for i in range(3)]
    r = client.post(f"/api/enroll/{NOT_ENROLLED}", files=files)
    assert r.status_code == 200 and r.json()["samples"] == 3
    assert next(c for c in client.get("/api/customers").json() if c["id"] == NOT_ENROLLED)["enrolled"]
    assert client.post(f"/api/enroll/{NOT_ENROLLED}", files=files[:2]).status_code == 400


def test_mask_pii():
    assert mask_pii("call me on 050 100 0001") == "call me on ******01"
    assert mask_pii("card 4111 1111 1111 1234") == "card ******34"
    assert mask_pii("born 24 January 1972, or 24/01/1972") == "born [DATE], or [DATE]"
    assert mask_pii("ending 5506, AED 4,250.75") == "ending 5506, AED 4,250.75"
