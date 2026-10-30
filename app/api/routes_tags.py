from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import TagCreate, TagOut
from app.services.tag_service import TagService

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = TagService(db)
    tags = svc.list_all(user.id)
    return [TagOut(id=t.id, name=t.name, color=t.color) for t in tags]


@router.post("", response_model=TagOut, status_code=201)
def create_tag(
    body: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = TagService(db)
    tag = svc.create(user.id, body.name, body.color)
    return TagOut(id=tag.id, name=tag.name, color=tag.color)


@router.delete("/{tag_id}", status_code=204)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = TagService(db)
    svc.delete(tag_id, user.id)
