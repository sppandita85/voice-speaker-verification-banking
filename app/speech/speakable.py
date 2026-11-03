"""Rewrite display text so TTS reads it naturally:

    "AED 4,250.75"  -> "four thousand two hundred and fifty dirhams and seventy-five fils"
    "25 November"   -> "the twenty-fifth of November"
    "ending 5506"   -> "ending five five zero six"
"""
import calendar
import re

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
ORDINAL_FIX = {"one": "first", "two": "second", "three": "third", "five": "fifth",
               "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}
_MONTHS = "|".join(calendar.month_name[1:])


def number_to_words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + (" and " + number_to_words(rest) if rest else "")
    for size, name in ((1_000_000_000, "billion"), (1_000_000, "million"), (1000, "thousand")):
        if n >= size:
            rest = n % size
            head = number_to_words(n // size) + " " + name
            if not rest:
                return head
            return head + (" and " if rest < 100 else " ") + number_to_words(rest)
    raise ValueError(n)


def ordinal_words(n: int) -> str:
    words = number_to_words(n)
    head, _, last = words.rpartition("-")
    if last in ORDINAL_FIX:
        last = ORDINAL_FIX[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return f"{head}-{last}" if head else last


def _amount(m: re.Match) -> str:
    dirhams = int(m.group(1).replace(",", ""))
    fils = int(m.group(2) or 0)
    text = f"{number_to_words(dirhams)} dirham{'s' if dirhams != 1 else ''}"
    if fils:
        text += f" and {number_to_words(fils)} fils"
    return text


def to_speech(text: str, language: str = "en") -> str:
    if language != "en":
        return text  # other languages: add rules here
    text = re.sub(r"AED\s?([\d,]+)(?:\.(\d{2}))?", _amount, text)
    text = re.sub(rf"\b(\d{{1,2}})\s+({_MONTHS})\b", lambda m: f"the {ordinal_words(int(m.group(1)))} of {m.group(2)}", text)
    text = re.sub(r"\b(\d{4})\b(?!\s*(dirham|fils))", lambda m: " ".join(number_to_words(int(d)) for d in m.group(1)), text)
    return text
