from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Many-to-many association table
letter_tag = Table(
    "letter_tag",
    Base.metadata,
    Column("letter_id", Integer, ForeignKey("letter.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Das Saganta-Konto, zu dem dieses Postfach gehoert (better-auth `user.id`).
    #
    # Bewusst ein zusaetzliches Feld und keine neue Mandantenspalte auf jeder
    # Tabelle: die Isolation ueber `user_id` gab es hier von Anfang an und sie
    # traegt. Was fehlte, war eine **gemeinsame Identitaet** mit dem Rest der
    # Suite. Diese Zeile ist genau diese Bruecke, und sie laesst jede bestehende
    # Abfrage unveraendert.
    #
    # Nullable, weil die drei Alt-Konten aus dem Maerz kein Saganta-Konto haben.
    # Unique, damit nicht zwei Postfaecher an demselben Saganta-Konto haengen.
    sub: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    letters: Mapped[list["Letter"]] = relationship(
        "Letter", back_populates="user", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class Letter(Base):
    __tablename__ = "letter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    sender: Mapped[str | None] = mapped_column(String(300), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    received_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    letter_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")  # none|processing|done|error
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paperless_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # task-uuid initial, später doc-id
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # soft-delete; None = aktiv
    correspondent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("correspondent.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("account.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="letters")
    correspondent: Mapped["Correspondent | None"] = relationship("Correspondent", back_populates="letters")
    files: Mapped[list["LetterFile"]] = relationship(
        "LetterFile", back_populates="letter", cascade="all, delete-orphan",
        order_by="LetterFile.page_number",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary=letter_tag, back_populates="letters"
    )


class LetterFile(Base):
    __tablename__ = "letter_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    letter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("letter.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    letter: Mapped["Letter"] = relationship("Letter", back_populates="files")


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="tags")
    letters: Mapped[list["Letter"]] = relationship(
        "Letter", secondary=letter_tag, back_populates="tags"
    )


class Correspondent(Base):
    __tablename__ = "correspondent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(),
    )

    letters: Mapped[list["Letter"]] = relationship("Letter", back_populates="correspondent")


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    correspondent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("correspondent.id", ondelete="SET NULL"), nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str | None] = mapped_column(String(60), nullable=True)  # Strom/Gas/Internet/Handy/Versicherung/Streaming/...
    contract_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    monthly_amount: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notice_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(),
    )

    correspondent: Mapped["Correspondent | None"] = relationship("Correspondent")
