"""Fake speech providers so tests and the UI run without any models.

FakeSTT treats the uploaded bytes as the transcript; FakeVoiceID returns a fixed score
that tests can change with `next_score`."""
import hashlib
import io
import wave

from app.speech.base import AudioClip


class FakeSTT:
    model_name = "fake-stt"

    def transcribe(self, clip: AudioClip, language: str) -> str:
        try:
            return clip.raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""


class FakeTTS:
    def synthesize(self, text: str, language: str) -> bytes:
        """A short silent WAV, so the browser still has something to play."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 1600)
        return buf.getvalue()


class FakeVoiceID:
    model_name = "fake-voiceid"

    def __init__(self, score: float = 0.8):
        self.default_score = score
        self.next_score: float | None = None

    def duration(self, clip: AudioClip) -> float | None:
        return None  # unknown: skip the "too short" check

    def embed(self, clip: AudioClip) -> list[float]:
        digest = hashlib.sha256(clip.raw).digest()
        return [b / 255 for b in digest] * 6  # 192 values

    def score(self, clip: AudioClip, enrolled: list[float]) -> float:
        if self.next_score is not None:
            score, self.next_score = self.next_score, None
            return score
        return self.default_score
