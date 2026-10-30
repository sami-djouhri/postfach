"""Correspondent-CRUD für Saganta-Document-Engine."""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Correspondent, User
from app.services import correspondent_service

router = APIRouter(prefix="/api/correspondents", tags=["correspondents"])


@router.get("")
def list_correspondents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return correspondent_service.list_with_counts(db, user.id)


@router.get("/{correspondent_id}")
def get_correspondent(
    correspondent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.get(Correspondent, correspondent_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="correspondent not found")
    return {
        "id": c.id, "name": c.name, "normalized": c.normalized,
        "address": c.address, "contact_info": c.contact_info, "notes": c.notes,
    }


@router.patch("/{correspondent_id}")
def patch_correspondent(
    correspondent_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.get(Correspondent, correspondent_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="correspondent not found")
    allowed = {"name", "address", "contact_info", "notes"}
    unknown = set(payload.keys()) - allowed
    if unknown:
        raise HTTPException(status_code=400, detail=f"unsupported: {sorted(unknown)}")
    if "name" in payload and payload["name"]:
        c.name = str(payload["name"])[:300]
        c.normalized = correspondent_service.normalize_name(c.name)
    for k in ("address", "contact_info", "notes"):
        if k in payload:
            setattr(c, k, payload[k])
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name, "normalized": c.normalized}


@router.post("/{correspondent_id}/merge")
def merge_correspondents(
    correspondent_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target_id = payload.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id required")
    try:
        moved = correspondent_service.merge(db, user.id, correspondent_id, int(target_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"moved_letters": moved, "target_id": target_id}
