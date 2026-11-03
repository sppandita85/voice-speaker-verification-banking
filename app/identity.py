"""Mobile number helpers. Numbers are normalised to 9715XXXXXXXX before hashing."""
import hashlib
import re


def normalize_mobile(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00971"):
        digits = digits[2:]
    if digits.startswith("971"):
        rest = digits[3:]
    elif digits.startswith("0"):
        rest = digits[1:]
    else:
        rest = digits
    if len(rest) == 9 and rest.startswith("5"):
        return "971" + rest
    return None


def hash_mobile(normalized: str, salt: str) -> str:
    return hashlib.sha256((salt + normalized).encode()).hexdigest()


def mask_mobile(normalized: str) -> str:
    # 971501000001 -> +971 50 XXX XX01
    return f"+971 {normalized[3:5]} XXX XX{normalized[-2:]}"
