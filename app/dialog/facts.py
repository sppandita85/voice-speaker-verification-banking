"""Facts come from the database, never from the LLM. Code formats them and writes the draft reply."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.llm.schemas import Intent
from app.models import Card, Statement


def format_aed(amount: Decimal) -> str:
    return f"AED {amount:,.2f}"


def format_day_month(d: date) -> str:
    return f"{d.day} {d:%B}"


def fils_to_aed(fils: int) -> Decimal:
    return (Decimal(fils) / 100).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class CardFacts:
    last4: str
    status: str
    outstanding: Decimal
    minimum_due: Decimal
    due_date: date
    is_overdue: bool

    @classmethod
    def from_db(cls, card: Card, statement: Statement) -> "CardFacts":
        return cls(
            last4=card.last4,
            status=card.status,
            outstanding=fils_to_aed(statement.outstanding_fils),
            minimum_due=fils_to_aed(statement.minimum_due_fils),
            due_date=statement.due_date,
            is_overdue=statement.is_overdue,
        )

    @property
    def zero_balance(self) -> bool:
        return self.outstanding == 0

    @property
    def blocked(self) -> bool:
        return self.status == "blocked"

    # What a correct reply must contain (used by the checker)
    def required_amounts(self, intent: Intent) -> set[Decimal]:
        if self.zero_balance:
            return set()
        amounts = set()
        if intent in (Intent.CARD_BALANCE, Intent.BOTH):
            amounts.add(self.outstanding)
        if intent in (Intent.DUE_DATE, Intent.BOTH):
            amounts.add(self.minimum_due)
        return amounts

    def requires_due_date(self, intent: Intent) -> bool:
        return not self.zero_balance and intent in (Intent.DUE_DATE, Intent.BOTH)

    def required_words(self) -> list[str]:
        words = []
        if self.blocked:
            words.append("blocked")
        if self.is_overdue and not self.zero_balance:
            words.append("overdue")
        return words

    def draft_reply(self, intent: Intent) -> str:
        """The deterministic answer. Spoken as-is if the LLM's version fails the checker."""
        parts = []
        if self.blocked:
            parts.append(f"Your card ending {self.last4} is currently blocked.")
        if self.zero_balance:
            parts.append(f"Your card ending {self.last4} has no outstanding balance, so no payment is due.")
            return " ".join(parts)

        bal, mini, due = format_aed(self.outstanding), format_aed(self.minimum_due), format_day_month(self.due_date)
        if intent in (Intent.CARD_BALANCE, Intent.BOTH):
            parts.append(f"The outstanding balance on your card ending {self.last4} is {bal}.")
        if intent in (Intent.DUE_DATE, Intent.BOTH):
            if self.is_overdue:
                parts.append(f"Your payment is overdue. The minimum payment of {mini} was due on {due}.")
            else:
                parts.append(f"The minimum payment of {mini} is due on {due}.")
        elif self.is_overdue:
            parts.append("Your payment is overdue.")
        return " ".join(parts)

    def llm_payload(self, intent: Intent) -> dict:
        """Everything the LLM may use. It gets the draft and must keep its facts."""
        payload = {"card": f"ending {self.last4}", "draft": self.draft_reply(intent)}
        if not self.zero_balance:
            if intent in (Intent.CARD_BALANCE, Intent.BOTH):
                payload["outstanding_balance"] = format_aed(self.outstanding)
            if intent in (Intent.DUE_DATE, Intent.BOTH):
                payload["minimum_payment"] = format_aed(self.minimum_due)
                payload["due_date"] = format_day_month(self.due_date)
        payload["must_mention"] = self.required_words()
        return payload
