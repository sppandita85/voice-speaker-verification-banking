"""Voice ID with SpeechBrain ECAPA-TDNN: a 192-number embedding per recording, compared by cosine."""
import warnings

from app.dialog.verification import cosine
from app.speech.base import AudioClip


class EcapaVoiceID:
    def __init__(self, source: str, savedir: str):
        warnings.filterwarnings("ignore", category=FutureWarning)  # torch/speechbrain deprecation noise
        from speechbrain.inference.speaker import EncoderClassifier

        self.model = EncoderClassifier.from_hparams(source=source, savedir=savedir, run_opts={"device": "cpu"})
        self.model_name = source.split("/")[-1]

    def duration(self, clip: AudioClip) -> float:
        return clip.seconds

    def embed(self, clip: AudioClip) -> list[float]:
        import torch

        wav = torch.from_numpy(clip.samples).unsqueeze(0)
        with torch.no_grad():
            embedding = self.model.encode_batch(wav)
        return embedding.squeeze().tolist()

    def score(self, clip: AudioClip, enrolled: list[float]) -> float:
        return cosine(self.embed(clip), enrolled)
