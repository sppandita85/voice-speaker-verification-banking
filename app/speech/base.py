"""An uploaded recording. Decoding (webm/ogg/wav -> 16 kHz mono) happens once, on first use."""
import io

SAMPLE_RATE = 16000


class AudioClip:
    def __init__(self, raw: bytes):
        self.raw = raw
        self._samples = None

    @property
    def samples(self):
        if self._samples is None:
            from faster_whisper.audio import decode_audio  # PyAV under the hood, no ffmpeg needed

            self._samples = decode_audio(io.BytesIO(self.raw), sampling_rate=SAMPLE_RATE)
        return self._samples

    @property
    def seconds(self) -> float:
        return len(self.samples) / SAMPLE_RATE
