"""Download the local models into ./models (about 600 MB in total).

    python scripts/download_models.py

- Whisper (faster-whisper, size from WHISPER_MODEL) -> Hugging Face cache
- ECAPA speaker model (speechbrain/spkrec-ecapa-voxceleb) -> models/ecapa
- Piper English voice (en_US-lessac-medium)        -> models/piper
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

PIPER_REPO, PIPER_DIR = "rhasspy/piper-voices", "en/en_US/lessac/medium/"
PIPER_FILES = ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"]


def main() -> None:
    settings = get_settings()

    print(f"Whisper '{settings.whisper_model}'...")
    from faster_whisper import WhisperModel

    WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")

    print("ECAPA speaker model...")
    from app.speech.voiceid import EcapaVoiceID

    EcapaVoiceID(settings.ecapa_source, settings.ecapa_savedir)

    voice_path = Path(settings.piper_voice_en)
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    for name in PIPER_FILES:
        target = voice_path.parent / name
        if not target.exists():
            print(f"Piper voice {name}...")
            from huggingface_hub import hf_hub_download

            shutil.copy(hf_hub_download(PIPER_REPO, PIPER_DIR + name, revision="v1.0.0"), target)

    print("All models ready.")


if __name__ == "__main__":
    main()
