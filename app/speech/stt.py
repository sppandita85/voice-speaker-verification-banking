"""Speech-to-text with faster-whisper (runs on CPU, int8)."""
from app.speech.base import AudioClip

# A hint that makes Whisper write numbers as digits, per language.
INITIAL_PROMPTS = {
    "en": "A call to Demo Bank about a credit card balance and due date. "
          "Numbers are written as digits, for example 050 123 4567, card ending 1234, born 5 March 1990.",
}


class WhisperSTT:
    def __init__(self, size: str, device: str = "cpu", compute_type: str = "int8"):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(size, device=device, compute_type=compute_type)
        self.model_name = f"faster-whisper-{size}"

    def transcribe(self, clip: AudioClip, language: str) -> str:
        segments, _info = self.model.transcribe(
            clip.samples,
            language=language,
            beam_size=1,
            vad_filter=True,
            initial_prompt=INITIAL_PROMPTS.get(language),
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
