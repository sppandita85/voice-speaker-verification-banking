"""Prompts live in prompts/<language>/<name>.<version>.txt. The version id is logged with every turn."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@dataclass(frozen=True)
class Prompt:
    text: str
    version_id: str  # e.g. "intent.en.v1"


@lru_cache
def load_prompt(name: str, language: str, version: str) -> Prompt:
    path = PROMPTS_DIR / language / f"{name}.{version}.txt"
    return Prompt(path.read_text(encoding="utf-8"), f"{name}.{language}.{version}")
