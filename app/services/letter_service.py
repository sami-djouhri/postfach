import os
from datetime import datetime, timezone
import shutil

from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.domain import DomainError
from app.models import Letter, LetterFile, Tag, letter_tag


class LetterService:
    def __init__(self, db: Session):
        self.db = db

    def list_all(
        self,
        user_id: int,
        category: str | None = None,
        is_archived: bool | None = None,
        search: str | None = None,
        tag_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
        include_snoozed: bool = False,
        show_deleted: bool = False,
        senders: list[str] | None = None,
        letter_date_from: str | None = None,
        letter_date_to: str | None = None,
        tag_ids_all: list[int] | None = None,
    ) -> list[dict]:
        stmt = (
            select(Letter)
            .where(Letter.user_id == user_id)
            .options(joinedload(Letter.tags), joinedload(Letter.files))
        )
        if show_deleted:
            stmt = stmt.where(Letter.deleted_at.is_not(None))
        else:
            stmt = stmt.where(Letter.deleted_at.is_(None))
        if category:
            stmt = stmt.where(Letter.category == category)
        if is_archived is not None:
            stmt = stmt.where(Letter.is_archived == is_archived)
        if not include_snoozed:
            now = datetime.now(timezone.utc)
            stmt = stmt.where(or_(Letter.snoozed_until.is_(None), Letter.snoozed_until <= now))
        if tag_id:
            stmt = stmt.where(Letter.tags.any(Tag.id == tag_id))
        if senders:
            stmt = stmt.where(Letter.sender.in_(senders))
        if letter_date_from:
            stmt = stmt.where(Letter.letter_date >= letter_date_from)
        if letter_date_to:
            stmt = stmt.where(Letter.letter_date <= letter_date_to)
        if tag_ids_all:
            # JEDER der gegebenen Tags muss am Letter sein → eigene any() pro Tag.
            for tid in tag_ids_all:
                stmt = stmt.where(Letter.tags.any(Tag.id == tid))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Letter.title.ilike(pattern),
                    Letter.sender.ilike(pattern),
                    Letter.ocr_text.ilike(pattern),
                    Letter.notes.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Letter.created_at.desc()).offset(skip).limit(limit)
        letters = self.db.execute(stmt).unique().scalars().all()
        return [
            {
                "letter": l,
                "file_count": len(l.files),
            }
            for l in letters
        ]

    def get(self, letter_id: int, user_id: int) -> Letter:
        letter = self.db.execute(
            select(Letter)
            .where(Letter.id == letter_id, Letter.user_id == user_id)
            .options(joinedload(Letter.files), joinedload(Letter.tags))
        ).unique().scalar_one_or_none()
        if not letter:
            raise DomainError("Brief nicht gefunden")
        return letter

    def create(self, user_id: int, title: str, sender: str | None = None,
               category: str | None = None, received_date: str | None = None,
               letter_date: str | None = None, notes: str | None = None,
               tag_ids: list[int] | None = None) -> Letter:
        letter = Letter(
            user_id=user_id,
            title=title,
            sender=sender,
            category=category,
            received_date=received_date,
            letter_date=letter_date,
            notes=notes,
        )
        if tag_ids:
            tags = self.db.execute(
                select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
            ).scalars().all()
            letter.tags = list(tags)
        self.db.add(letter)
        self.db.commit()
        self.db.refresh(letter)
        return letter

    def update(self, letter_id: int, user_id: int, **kwargs) -> Letter:
        letter = self.get(letter_id, user_id)
        tag_ids = kwargs.pop("tag_ids", None)
        # snoozed_until: explizites null bedeutet "unsnooze" und muss durchkommen.
        # Caller liefert nur Keys mit, die im Payload waren (exclude_unset=True),
        # daher dürfen wir hier nicht generell None-Werte filtern.
        nullable_explicit = {"snoozed_until", "paperless_id"}
        for key, value in kwargs.items():
            if key in nullable_explicit or value is not None:
                setattr(letter, key, value)

        if tag_ids is not None:
            tags = self.db.execute(
                select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
            ).scalars().all()
            letter.tags = list(tags)

        self.db.commit()
        self.db.refresh(letter)
        return letter

    def delete(self, letter_id: int, user_id: int) -> None:
        """Soft-Delete: setzt deleted_at, Files bleiben auf Disk bis hard_delete."""
        from datetime import datetime, timezone
        letter = self.get(letter_id, user_id)
        if letter.deleted_at is not None:
            return  # idempotent
        letter.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def restore(self, letter_id: int, user_id: int) -> Letter:
        letter = self.get(letter_id, user_id)
        letter.deleted_at = None
        self.db.commit()
        self.db.refresh(letter)
        return letter

    def hard_delete(self, letter_id: int, user_id: int) -> None:
        letter = self.get(letter_id, user_id)
        user_dir = os.path.join(settings.FILES_DIR, str(user_id))
        for f in letter.files:
            file_path = os.path.join(user_dir, f.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        self.db.delete(letter)
        self.db.commit()

    def get_file(self, letter_id: int, file_id: int, user_id: int) -> LetterFile:
        letter = self.get(letter_id, user_id)
        for f in letter.files:
            if f.id == file_id:
                return f
        raise DomainError("Datei nicht gefunden")

    def delete_file(self, letter_id: int, file_id: int, user_id: int) -> None:
        file = self.get_file(letter_id, file_id, user_id)
        file_path = os.path.join(settings.FILES_DIR, str(user_id), file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        self.db.delete(file)
        self.db.commit()

    def count_by_user(self, user_id: int) -> int:
        return self.db.execute(
            select(func.count(Letter.id)).where(Letter.user_id == user_id, Letter.deleted_at.is_(None))
        ).scalar() or 0

    def count_archived(self, user_id: int) -> int:
        return self.db.execute(
            select(func.count(Letter.id)).where(
                Letter.user_id == user_id, Letter.is_archived == True, Letter.deleted_at.is_(None)
            )
        ).scalar() or 0

    def count_pending_ocr(self, user_id: int) -> int:
        return self.db.execute(
            select(func.count(Letter.id)).where(
                Letter.user_id == user_id, Letter.ocr_status == "pending", Letter.deleted_at.is_(None)
            )
        ).scalar() or 0

    def category_counts(self, user_id: int) -> dict[str, int]:
        rows = self.db.execute(
            select(Letter.category, func.count(Letter.id))
            .where(Letter.user_id == user_id, Letter.category.isnot(None), Letter.deleted_at.is_(None))
            .group_by(Letter.category)
        ).all()
        return {cat: count for cat, count in rows}
