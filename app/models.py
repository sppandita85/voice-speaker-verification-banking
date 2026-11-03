"""Database tables.

Money is stored as integer fils (1 AED = 100 fils) so there is never any float rounding.
The full mobile number is never stored: only a salted hash (for lookup) and a masked copy.
"""
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    mobile_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mobile_masked: Mapped[str] = mapped_column(String(20))
    dob: Mapped[date] = mapped_column(Date)
    preferred_lang: Mapped[str] = mapped_column(String(5), default="en")
    demo_note: Mapped[str] = mapped_column(String(100), default="")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    cards: Mapped[list["Card"]] = relationship(back_populates="customer", order_by="Card.id")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    last4: Mapped[str] = mapped_column(String(4))
    product_name: Mapped[str] = mapped_column(String(50))
    credit_limit_fils: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10))  # active | blocked

    customer: Mapped[Customer] = relationship(back_populates="cards")
    statements: Mapped[list["Statement"]] = relationship(order_by="Statement.statement_date")


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    statement_date: Mapped[date] = mapped_column(Date)
    outstanding_fils: Mapped[int] = mapped_column(BigInteger)
    minimum_due_fils: Mapped[int] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False)


class Voiceprint(Base):
    __tablename__ = "voiceprints"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), unique=True)
    embedding: Mapped[list[float]] = mapped_column(JSON)  # 192 floats from ECAPA
    sample_count: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), default="in_progress")
    handover_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)

    turns: Mapped[list["Turn"]] = relationship(order_by="Turn.seq")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))  # state when the turn arrived
    transcript_masked: Mapped[str] = mapped_column(Text, default="")
    intent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    voice_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verify_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reply_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # llm | template
    llm_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bot_reply_masked: Mapped[str] = mapped_column(Text, default="")
    stt_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
