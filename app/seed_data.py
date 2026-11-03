"""Synthetic demo data. No real people, banks or cards.

Used by scripts/seed.py and by the tests, so both see the same customers.
"""
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.identity import hash_mobile, mask_mobile, normalize_mobile
from app.models import Card, Customer, Statement, Voiceprint

NAMES = [
    "Aisha Al Mansoori", "Omar Haddad", "Priya Nair", "Rashid Al Suwaidi", "Fatima Khan",
    "Daniel Okafor", "Mariam Al Hashimi", "Arjun Mehta", "Layla Saeed", "Yousef Al Zaabi",
    "Sara Ibrahim", "Khalid Rahman", "Noura Al Ketbi", "Vikram Iyer", "Hessa Al Mazrouei",
    "Joseph Mathew", "Reem Abdullah", "Imran Siddiqui", "Maitha Al Nuaimi", "Carlos Mendes",
]
PRODUCTS = ["Desert Rewards Visa", "Falcon Platinum Mastercard", "Skyline Cashback Card"]

# Edge cases, by customer number (1-based)
STANDARD, TWO_CARDS, OVERDUE, ZERO_BALANCE, BLOCKED, NOT_ENROLLED = 1, 2, 3, 4, 5, 6
NOTES = {
    STANDARD: "standard (AED 4,250.75)",
    TWO_CARDS: "two cards: asks which one",
    OVERDUE: "payment overdue",
    ZERO_BALANCE: "zero balance",
    BLOCKED: "card blocked",
    NOT_ENROLLED: "no voiceprint: step-up only",
}


@dataclass
class DemoCustomer:
    """The presenter's cheat sheet row (written to data/demo_customers.csv)."""

    number: int
    name: str
    mobile: str
    dob: date
    card_last4: list[str]
    note: str


def demo_mobile(number: int) -> str:
    return f"050 100 00{number:02d}"


def minimum_due(outstanding: Decimal) -> Decimal:
    """5% of the balance, at least AED 100, never more than the balance."""
    five_pct = (outstanding * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(outstanding, max(five_pct, Decimal("100.00")))


def to_fils(aed: Decimal) -> int:
    return int((aed * 100).to_integral_value())


def _statement(outstanding: Decimal, today: date, overdue: bool = False) -> Statement:
    if overdue:
        statement_date, due = today - timedelta(days=35), today - timedelta(days=5)
    else:
        statement_date, due = today - timedelta(days=10), today + timedelta(days=15)
    return Statement(
        statement_date=statement_date,
        outstanding_fils=to_fils(outstanding),
        minimum_due_fils=to_fils(minimum_due(outstanding)),
        due_date=due,
        is_overdue=overdue,
    )


def seed(session: Session, salt: str, today: date | None = None, fake_voiceprints: bool = False) -> list[DemoCustomer]:
    """Insert ~20 customers with cards and statements. Expects empty tables."""
    rng = random.Random(42)
    today = today or date.today()
    used_last4: set[str] = set()
    demo: list[DemoCustomer] = []

    def new_last4() -> str:
        while True:
            value = f"{rng.randint(1000, 9999)}"
            if value not in used_last4:
                used_last4.add(value)
                return value

    for number, name in enumerate(NAMES, start=1):
        mobile = demo_mobile(number)
        normalized = normalize_mobile(mobile)
        dob = date(rng.randint(1965, 2000), rng.randint(1, 12), rng.randint(1, 28))
        customer = Customer(
            full_name=name,
            mobile_hash=hash_mobile(normalized, salt),
            mobile_masked=mask_mobile(normalized),
            dob=dob,
            preferred_lang="en",
            demo_note=NOTES.get(number, "standard"),
        )
        session.add(customer)

        card_count = 2 if number == TWO_CARDS else 1
        for i in range(card_count):
            card = Card(
                last4=new_last4(),
                product_name=PRODUCTS[(number + i) % len(PRODUCTS)],
                credit_limit_fils=to_fils(Decimal(rng.choice([10000, 15000, 25000, 40000]))),
                status="blocked" if number == BLOCKED else "active",
            )
            customer.cards.append(card)

            if number == STANDARD:
                outstanding = Decimal("4250.75")
            elif number == ZERO_BALANCE:
                outstanding = Decimal("0.00")
            else:
                outstanding = Decimal(rng.randint(30000, 1200000)) / 100
            card.statements.append(_statement(outstanding, today, overdue=(number == OVERDUE)))

        if fake_voiceprints and number != NOT_ENROLLED:
            session.flush()
            session.add(Voiceprint(customer_id=customer.id, embedding=[0.0] * 192, sample_count=0, model="fake"))

        demo.append(DemoCustomer(number, name, mobile, dob, [c.last4 for c in customer.cards], customer.demo_note))

    session.commit()
    return demo
