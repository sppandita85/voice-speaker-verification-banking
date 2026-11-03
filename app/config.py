"""All settings come from environment variables / .env (see .env.example)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://voicebot:voicebot@localhost:5434/voicebot"
    mobile_hash_salt: str = "demo-salt-change-me"

    language: str = "en"

    speech_provider: str = "real"  # real | fake
    llm_provider: str = "ollama"  # ollama | fake

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    piper_voice_en: str = "models/piper/en_US-lessac-medium.onnx"

    ecapa_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    ecapa_savedir: str = "models/ecapa"
    voice_accept_threshold: float = 0.55
    voice_stepup_threshold: float = 0.40
    voice_min_seconds: float = 1.5
    max_verify_attempts: int = 3
    lock_minutes: int = 5
    fake_voice_score: float = 0.80

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    prompt_version: str = "v1"

    def piper_voice(self, language: str) -> str:
        return getattr(self, f"piper_voice_{language}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
