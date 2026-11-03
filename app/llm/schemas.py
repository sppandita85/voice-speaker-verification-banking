"""What the LLM is allowed to return. Anything that does not validate is rejected."""
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    CARD_BALANCE = "CARD_BALANCE"
    DUE_DATE = "DUE_DATE"
    BOTH = "BOTH"
    OTHER = "OTHER"
    AGENT = "AGENT"
    REPEAT = "REPEAT"
    GOODBYE = "GOODBYE"


ANSWERABLE = {Intent.CARD_BALANCE, Intent.DUE_DATE, Intent.BOTH}


class IntentResult(BaseModel):
    intent: Intent
    confidence: float = Field(default=1.0, ge=0, le=1)


class ReplyResult(BaseModel):
    reply: str = Field(min_length=1, max_length=400)


@dataclass
class LLMResult:
    value: Any
    model: str
    prompt_version: str | None
    ms: int
