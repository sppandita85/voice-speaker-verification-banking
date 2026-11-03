"""Database reads and the few writes the bot needs."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Customer, Statement, Voiceprint, utcnow


def find_customer_by_mobile_hash(db: Session, mobile_hash: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.mobile_hash == mobile_hash))


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def list_customers(db: Session) -> list[Customer]:
    return list(db.scalars(select(Customer).order_by(Customer.id)))


def cards_for_customer(db: Session, customer_id: int) -> list[Card]:
    return list(db.scalars(select(Card).where(Card.customer_id == customer_id).order_by(Card.id)))


def latest_statement(db: Session, card_id: int) -> Statement | None:
    return db.scalar(
        select(Statement).where(Statement.card_id == card_id).order_by(Statement.statement_date.desc()).limit(1)
    )


def get_voiceprint(db: Session, customer_id: int) -> Voiceprint | None:
    return db.scalar(select(Voiceprint).where(Voiceprint.customer_id == customer_id))


def save_voiceprint(db: Session, customer_id: int, embedding: list[float], sample_count: int, model: str) -> None:
    existing = get_voiceprint(db, customer_id)
    if existing:
        db.delete(existing)
        db.flush()
    db.add(Voiceprint(customer_id=customer_id, embedding=embedding, sample_count=sample_count, model=model))
    db.commit()


def is_locked(customer: Customer, now: datetime | None = None) -> bool:
    return customer.locked_until is not None and customer.locked_until > (now or utcnow())


def lock_customer(db: Session, customer_id: int, minutes: int) -> None:
    customer = db.get(Customer, customer_id)
    customer.locked_until = utcnow() + timedelta(minutes=minutes)
    db.commit()


def unlock_customer(db: Session, customer_id: int) -> None:
    customer = db.get(Customer, customer_id)
    customer.locked_until = None
    db.commit()
