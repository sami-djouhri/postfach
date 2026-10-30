from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import DomainError
from app.models import Tag


class TagService:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self, user_id: int) -> list[Tag]:
        return self.db.execute(
            select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
        ).scalars().all()

    def get(self, tag_id: int, user_id: int) -> Tag:
        tag = self.db.execute(
            select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        ).scalar_one_or_none()
        if not tag:
            raise DomainError("Tag nicht gefunden")
        return tag

    def create(self, user_id: int, name: str, color: str = "#6366f1") -> Tag:
        existing = self.db.execute(
            select(Tag).where(Tag.user_id == user_id, Tag.name == name)
        ).scalar_one_or_none()
        if existing:
            raise DomainError(f"Tag '{name}' existiert bereits")

        tag = Tag(user_id=user_id, name=name, color=color)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def delete(self, tag_id: int, user_id: int) -> None:
        tag = self.get(tag_id, user_id)
        self.db.delete(tag)
        self.db.commit()
