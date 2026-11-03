"""Pick real or fake providers from settings. Real ones load their models once, at startup."""
from dataclasses import dataclass

from app.config import Settings


@dataclass
class Providers:
    stt: object
    tts: object
    voice: object
    llm: object


def build_providers(settings: Settings) -> Providers:
    if settings.speech_provider == "fake":
        from app.speech.fakes import FakeSTT, FakeTTS, FakeVoiceID

        stt, tts, voice = FakeSTT(), FakeTTS(), FakeVoiceID(settings.fake_voice_score)
    else:
        from app.speech.stt import WhisperSTT
        from app.speech.tts import PiperTTS
        from app.speech.voiceid import EcapaVoiceID

        stt = WhisperSTT(settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
        tts = PiperTTS({settings.language: settings.piper_voice(settings.language)})
        voice = EcapaVoiceID(settings.ecapa_source, settings.ecapa_savedir)

    if settings.llm_provider == "fake":
        from app.llm.fake import FakeLLM

        llm = FakeLLM()
    else:
        from app.llm.ollama import OllamaLLM

        llm = OllamaLLM(settings.ollama_url, settings.ollama_model, settings.prompt_version)
    return Providers(stt, tts, voice, llm)
