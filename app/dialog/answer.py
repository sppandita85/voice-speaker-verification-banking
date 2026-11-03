"""Turn verified facts into the spoken answer: LLM phrasing, then the checker, else the draft."""
import logging
from dataclasses import dataclass, field

from app.dialog.checker import check_reply
from app.dialog.facts import CardFacts
from app.llm.schemas import Intent

log = logging.getLogger(__name__)


@dataclass
class Answer:
    text: str
    source: str  # "llm" or "template"
    model: str | None = None
    prompt_version: str | None = None
    ms: int | None = None
    checker_errors: list[str] = field(default_factory=list)


def compose_answer(llm, facts: CardFacts, intent: Intent, language: str) -> Answer:
    draft = facts.draft_reply(intent)
    try:
        result = llm.phrase_answer(facts.llm_payload(intent), language)
    except Exception as exc:  # LLM down or invalid JSON: the draft is still correct
        log.warning("LLM phrasing failed, using template: %s", exc)
        return Answer(draft, "template", checker_errors=[f"llm error: {exc}"])

    check = check_reply(result.value, facts, intent)
    if check.ok:
        return Answer(result.value, "llm", result.model, result.prompt_version, result.ms)
    log.warning("Checker rejected LLM reply %s; using template", check.errors)
    return Answer(draft, "template", result.model, result.prompt_version, result.ms, check.errors)
