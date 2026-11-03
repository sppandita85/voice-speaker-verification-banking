"""Voice ID decision: compare a cosine score with two thresholds."""
import math
from enum import Enum


class VoiceDecision(str, Enum):
    PASS = "pass"
    STEP_UP = "step_up"
    FAIL = "fail"


def decide(score: float, accept: float, step_up: float) -> VoiceDecision:
    if score >= accept:
        return VoiceDecision.PASS
    if score >= step_up:
        return VoiceDecision.STEP_UP
    return VoiceDecision.FAIL


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def average_embedding(embeddings: list[list[float]]) -> list[float]:
    """Enrollment voiceprint: the mean of the length-normalised sample embeddings."""
    normed = []
    for e in embeddings:
        n = math.sqrt(sum(x * x for x in e)) or 1.0
        normed.append([x / n for x in e])
    return [sum(col) / len(normed) for col in zip(*normed)]
