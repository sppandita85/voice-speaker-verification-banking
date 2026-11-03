"""An uploaded recording. Decoding (webm/ogg/wav -> 16 kHz mono float32) happens once, on first use."""
import io

SAMPLE_RATE = 16000


def decode_audio(raw: bytes):
    """Decode any container the browser sends with PyAV (bundled FFmpeg, no system ffmpeg needed)."""
    import av
    import numpy as np

    chunks = []
    with av.open(io.BytesIO(raw)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(audio=0):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0


class AudioClip:
    def __init__(self, raw: bytes):
        self.raw = raw
        self._samples = None

    @property
    def samples(self):
        if self._samples is None:
            self._samples = decode_audio(self.raw)
        return self._samples

    @property
    def seconds(self) -> float:
        return len(self.samples) / SAMPLE_RATE
