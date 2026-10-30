from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import LetterListOut, TagOut
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[LetterListOut])
def search(
    q: str = Query(min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = SearchService(db)
    letters = svc.search(user.id, q, skip=skip, limit=limit)
    return [
        LetterListOut(
            id=l.id,
            title=l.title,
            sender=l.sender,
            category=l.category,
            received_date=l.received_date,
            ocr_status=l.ocr_status,
            is_archived=l.is_archived,
            created_at=l.created_at,
            file_count=len(l.files),
            tags=[TagOut(id=t.id, name=t.name, color=t.color) for t in l.tags],
        )
        for l in letters
    ]
