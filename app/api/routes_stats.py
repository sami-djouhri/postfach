from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import LetterListOut, StatsOut, TagOut
from app.services.letter_service import LetterService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    recent_items = svc.list_all(user_id=user.id, limit=5)
    recent = [
        LetterListOut(
            id=item["letter"].id,
            title=item["letter"].title,
            sender=item["letter"].sender,
            category=item["letter"].category,
            received_date=item["letter"].received_date,
            ocr_status=item["letter"].ocr_status,
            is_archived=item["letter"].is_archived,
            created_at=item["letter"].created_at,
            file_count=item["file_count"],
            tags=[TagOut(id=t.id, name=t.name, color=t.color) for t in item["letter"].tags],
        )
        for item in recent_items
    ]

    return StatsOut(
        total_letters=svc.count_by_user(user.id),
        archived_letters=svc.count_archived(user.id),
        pending_ocr=svc.count_pending_ocr(user.id),
        categories=svc.category_counts(user.id),
        recent_letters=recent,
    )
