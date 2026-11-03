import pytest

from app.dialog.verification import VoiceDecision, average_embedding, cosine, decide

ACCEPT, STEP_UP = 0.55, 0.40


@pytest.mark.parametrize(
    "score, expected",
    [
        (0.90, VoiceDecision.PASS),
        (0.55, VoiceDecision.PASS),  # exactly on the accept threshold passes
        (0.549, VoiceDecision.STEP_UP),
        (0.40, VoiceDecision.STEP_UP),  # exactly on the step-up threshold steps up
        (0.399, VoiceDecision.FAIL),
        (-0.2, VoiceDecision.FAIL),
    ],
)
def test_thresholds(score, expected):
    assert decide(score, ACCEPT, STEP_UP) == expected


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert cosine([0, 0], [1, 0]) == 0.0


def test_average_embedding_normalises_each_sample():
    avg = average_embedding([[2, 0], [0, 10]])
    assert avg == pytest.approx([0.5, 0.5])
