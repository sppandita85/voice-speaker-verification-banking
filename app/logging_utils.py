"""PII masking for everything that is logged or stored as a transcript."""
import calendar
import logging
import re

REDACTED = "[redacted: identification / verification answer]"

_MONTHS = "|".join(calendar.month_name[1:])
_DATE_WITH_YEAR = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?(?:\s+of)?\s+(?:{_MONTHS}),?\s+\d{{4}}\b"
    rf"|\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b"
    r"|\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_LONG_NUMBER = re.compile(r"\+?\d(?:[\s\-]?\d){6,}")  # 7+ digits: mobile or card numbers


def mask_pii(text: str) -> str:
    text = _DATE_WITH_YEAR.sub("[DATE]", text)
    return _LONG_NUMBER.sub(lambda m: "*" * 6 + re.sub(r"\D", "", m.group(0))[-2:], text)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
