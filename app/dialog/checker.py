"""Checks a reply before it is spoken: every amount and date must match the database facts,
the required facts must be present, and no other numbers may appear."""
import calendar
import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.dialog.facts import CardFacts
from app.llm.schemas import Intent

_MONTHS = "|".join(calendar.month_name[1:])
_ORD = r"(?:st|nd|rd|th)?"
DATE_RE = re.compile(
    rf"\b(?P<d1>\d{{1,2}}){_ORD}(?:\s+of)?\s+(?P<m1>{_MONTHS})(?:,?\s+(?P<y1>\d{{4}}))?\b"
    rf"|\b(?P<m2>{_MONTHS})\s+(?P<d2>\d{{1,2}}){_ORD}(?:,?\s+(?P<y2>\d{{4}}))?\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
NUMBER_WORDS_RE = re.compile(r"\b(hundred|thousand|million|billion|point)\b", re.IGNORECASE)
_MONTH_NUM = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}


@dataclass
class CheckResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def check_reply(reply: str, facts: CardFacts, intent: Intent) -> CheckResult:
    errors: list[str] = []

    # 1. Dates: each one must be the due date
    found_due_date = False
    for m in DATE_RE.finditer(reply):
        day = int(m.group("d1") or m.group("d2"))
        month = _MONTH_NUM[(m.group("m1") or m.group("m2")).lower()]
        year = m.group("y1") or m.group("y2")
        if (day, month) == (facts.due_date.day, facts.due_date.month) and (not year or int(year) == facts.due_date.year):
            found_due_date = True
        else:
            errors.append(f"wrong date: {m.group(0)!r}")
    rest = DATE_RE.sub(" ", reply)

    # 2. Numbers: each one must be a known amount or the card's last 4 digits
    allowed = {facts.outstanding, facts.minimum_due}
    found_amounts: set[Decimal] = set()
    for token in NUMBER_RE.findall(rest):
        token = token.rstrip(",")
        if token == facts.last4:
            continue
        value = Decimal(token.replace(",", ""))
        if value in allowed:
            found_amounts.add(value)
        else:
            errors.append(f"unknown number: {token!r}")
    if NUMBER_WORDS_RE.search(rest):
        errors.append("amounts must be written in digits")

    # 3. Required facts must be present
    for amount in facts.required_amounts(intent) - found_amounts:
        errors.append(f"missing amount: {amount}")
    if facts.requires_due_date(intent) and not found_due_date:
        errors.append("missing due date")
    for word in facts.required_words():
        if word not in reply.lower():
            errors.append(f"missing word: {word!r}")

    return CheckResult(ok=not errors, errors=errors)
