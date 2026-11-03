"""Pull mobile numbers, card digits and dates of birth out of transcripts.

Whisper usually writes digits ("050 100 0001") but callers also say "zero five zero, double one..."."""
import calendar
import re
from datetime import date

from app.identity import normalize_mobile

WORD_DIGITS = {
    "zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
REPEATERS = {"double": 2, "triple": 3}
_MONTHS = "|".join(calendar.month_name[1:])
_MONTH_NUM = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_ORD = r"(?:st|nd|rd|th)?"
DOB_PATTERNS = [
    # 24 January 1972 / 24th of January, 1972
    (re.compile(rf"\b(\d{{1,2}}){_ORD}(?:\s+of)?\s+({_MONTHS}),?\s+(\d{{4}})\b", re.I), ("d", "m", "y")),
    # January 24, 1972
    (re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}){_ORD},?\s+(\d{{4}})\b", re.I), ("m", "d", "y")),
    # 24/01/1972 (day first, as in the UAE)
    (re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b"), ("d", "m", "y")),
    # 1972-01-24
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
]


def spoken_digits(text: str) -> str:
    """'zero five zero, double one 23' -> '0501123'. Other words are ignored."""
    digits, repeat = [], 1
    for token in re.findall(r"[a-z]+|\d+", text.lower()):
        if token in REPEATERS:
            repeat = REPEATERS[token]
            continue
        if token.isdigit():
            digits.append(token[0] * repeat + token[1:])
        elif token in WORD_DIGITS:
            digits.append(WORD_DIGITS[token] * repeat)
        repeat = 1
    return "".join(digits)


def parse_mobile(text: str) -> str | None:
    return normalize_mobile(spoken_digits(text))


def find_dob(text: str) -> tuple[date | None, str]:
    """Return (date or None, text with the date removed)."""
    for pattern, order in DOB_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        parts = dict(zip(order, m.groups()))
        month = parts["m"]
        month = _MONTH_NUM[month.lower()] if not month.isdigit() else int(month)
        try:
            found = date(int(parts["y"]), month, int(parts["d"]))
        except ValueError:
            continue
        return found, text[: m.start()] + " " + text[m.end():]
    return None, text


def parse_step_up(text: str) -> tuple[str | None, date | None]:
    """'The last four digits are 5506 and I was born on 24 January 1972' -> ('5506', date(1972, 1, 24))."""
    dob, rest = find_dob(text)
    digits = spoken_digits(rest)
    last4 = digits[-4:] if len(digits) >= 4 else None
    return last4, dob


def parse_card_choice(text: str, last4s: list[str]) -> str | None:
    digits = spoken_digits(text)
    for last4 in last4s:
        if last4 in digits:
            return last4
    lowered = text.lower()
    for i, word in enumerate(["first", "second", "third"]):
        if re.search(rf"\b{word}\b", lowered) and i < len(last4s):
            return last4s[i]
    return None
