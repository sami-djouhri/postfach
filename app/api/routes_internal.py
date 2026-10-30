"""Internal API für system-internen Zugriff (knowledge-gateway, saganta-mail).

Auth: Bearer-Token aus env (KG_INTERNAL_TOKEN). Sucht über alle User-Briefe;
internal-Konsumenten sitzen in der Single-Tenant-Trust-Boundary des Homelabs.
"""
import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.models import Account, Letter, LetterFile

router = APIRouter(prefix="/api/internal", tags=["internal"])


def _check_token(authorization: str | None = Header(None)) -> None:
    if not settings.KG_INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail="internal API disabled")
    expected = f"Bearer {settings.KG_INTERNAL_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid token")


def _letter_list_dict(l: Letter) -> dict:
    return {
        "id": l.id,
        "title": l.title,
        "sender": l.sender,
        "category": l.category,
        "received_date": l.received_date,
        "letter_date": l.letter_date,
        "ocr_status": l.ocr_status,
        "is_archived": l.is_archived,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "summary": l.llm_summary,
        "analysis_status": l.analysis_status,
        "snoozed_until": l.snoozed_until.isoformat() if l.snoozed_until else None,
        "paperless_id": l.paperless_id,
        "file_count": len(l.files),
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in l.tags],
    }


def _letter_detail_dict(l: Letter) -> dict:
    d = _letter_list_dict(l)
    d.update(
        ocr_text=l.ocr_text,
        notes=l.notes,
        updated_at=l.updated_at.isoformat() if l.updated_at else None,
        files=[
            {
                "id": f.id,
                "filename": f.filename,
                "original_filename": f.original_filename,
                "content_type": f.content_type,
                "file_size": f.file_size,
                "page_number": f.page_number,
            }
            for f in l.files
        ],
    )
    return d


@router.get("/search")
def search(
    q: str = Query(min_length=1),
    limit: int = Query(20, ge=1, le=100),
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"
    stmt = (
        select(Letter)
        .where(
            or_(
                Letter.title.ilike(pattern),
                Letter.sender.ilike(pattern),
                Letter.ocr_text.ilike(pattern),
                Letter.notes.ilike(pattern),
                Letter.llm_summary.ilike(pattern),
            )
        )
        .options(joinedload(Letter.tags))
        .order_by(Letter.created_at.desc())
        .limit(limit)
    )
    letters = db.execute(stmt).unique().scalars().all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "sender": l.sender,
            "snippet": (l.llm_summary or l.notes or l.ocr_text or "")[:200],
            "received_at": l.received_date,
            "url": f"/letters/{l.id}",
        }
        for l in letters
    ]


@router.get("/stats")
def stats(
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Letter.id))) or 0
    archived = (
        db.scalar(select(func.count(Letter.id)).where(Letter.is_archived.is_(True))) or 0
    )
    pending_ocr = (
        db.scalar(
            select(func.count(Letter.id)).where(Letter.ocr_status.notin_(["completed", "done"]))
        )
        or 0
    )
    return {
        "total": total,
        "active": total - archived,
        "archived": archived,
        "pending_ocr": pending_ocr,
    }


@router.get("/letters")
def list_letters(
    category: str | None = Query(None),
    is_archived: bool | None = Query(None),
    search: str | None = Query(None),
    tag_id: int | None = Query(None),
    include_snoozed: bool = Query(False, description="Wenn False: filtert snoozed_until>now() raus."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Letter)
        .options(joinedload(Letter.tags), joinedload(Letter.files))
        .order_by(Letter.created_at.desc())
    )
    if category is not None:
        stmt = stmt.where(Letter.category == category)
    if is_archived is not None:
        stmt = stmt.where(Letter.is_archived == is_archived)
    if not include_snoozed:
        # Nullable column: 3-valued SQL logic, IS NULL muss explizit ge-or-t werden.
        now = datetime.now(timezone.utc)
        stmt = stmt.where(or_(Letter.snoozed_until.is_(None), Letter.snoozed_until <= now))
    if tag_id is not None:
        stmt = stmt.where(Letter.tags.any(id=tag_id))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Letter.title.ilike(pattern),
                Letter.sender.ilike(pattern),
                Letter.ocr_text.ilike(pattern),
                Letter.notes.ilike(pattern),
                Letter.llm_summary.ilike(pattern),
            )
        )
    stmt = stmt.offset(skip).limit(limit)
    letters = db.execute(stmt).unique().scalars().all()
    return [_letter_list_dict(l) for l in letters]


@router.get("/letters/{letter_id}")
def get_letter(
    letter_id: int,
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Letter)
        .where(Letter.id == letter_id)
        .options(joinedload(Letter.tags), joinedload(Letter.files))
    )
    letter = db.execute(stmt).unique().scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")
    return _letter_detail_dict(letter)


@router.patch("/letters/{letter_id}")
def patch_letter(
    letter_id: int,
    payload: dict = Body(...),
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    allowed = {"is_archived", "snoozed_until", "paperless_id"}
    unknown = set(payload.keys()) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported fields: {sorted(unknown)}; allowed: {sorted(allowed)}",
        )
    letter = db.get(Letter, letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")
    if "is_archived" in payload:
        letter.is_archived = bool(payload["is_archived"])
    if "snoozed_until" in payload:
        raw = payload["snoozed_until"]
        if raw is None:
            letter.snoozed_until = None
        else:
            try:
                # akzeptiert ISO-8601 mit/ohne Z
                v = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"snoozed_until: {exc}")
            letter.snoozed_until = v
    if "paperless_id" in payload:
        raw = payload["paperless_id"]
        letter.paperless_id = str(raw) if raw is not None else None
    db.commit()
    db.refresh(letter)
    return _letter_detail_dict(letter)


@router.get("/letters/{letter_id}/files/{file_id}")
def get_letter_file(
    letter_id: int,
    file_id: int,
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    letter_file = db.get(LetterFile, file_id)
    if not letter_file or letter_file.letter_id != letter_id:
        raise HTTPException(status_code=404, detail="file not found")
    letter = db.get(Letter, letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")
    file_path = os.path.join(settings.FILES_DIR, str(letter.user_id), letter_file.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="file missing on disk")
    return FileResponse(
        file_path,
        media_type=letter_file.content_type,
        filename=letter_file.original_filename,
    )


@router.post("/letters/{letter_id}/forward-to-paperless", status_code=200)
def forward_to_paperless(
    letter_id: int,
    payload: dict = Body(default_factory=dict),
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    """Forward letter (primary file) to Paperless. Idempotent: re-call wirft 409
    wenn `letter.paperless_id` bereits gesetzt ist."""
    from app.services.paperless_service import PaperlessForwardError, forward_letter

    stmt = (
        select(Letter)
        .where(Letter.id == letter_id)
        .options(joinedload(Letter.tags), joinedload(Letter.files))
    )
    letter = db.execute(stmt).unique().scalar_one_or_none()
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")
    if letter.paperless_id:
        raise HTTPException(
            status_code=409,
            detail={"reason": "already forwarded", "paperless_id": letter.paperless_id},
        )

    tag_ids = payload.get("tag_ids") or []
    summary = payload.get("summary")
    if not isinstance(tag_ids, list):
        raise HTTPException(status_code=400, detail="tag_ids must be a list")

    try:
        task_id = forward_letter(letter, tag_ids=tag_ids, summary=summary)
    except PaperlessForwardError as exc:
        # 503: Konfig fehlt, Datei weg, Upstream-Fehler. Caller (Saganta-UI)
        # entscheidet ob Retry sinnvoll.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    letter.paperless_id = task_id
    db.commit()
    db.refresh(letter)
    return {"paperless_task_id": task_id, "letter_id": letter.id}


@router.get("/accounts")
def internal_list_accounts(
    only_active: bool = Query(True),
    notice_within_days: int | None = Query(None, ge=1, le=730),
    _: None = Depends(_check_token),
    db: Session = Depends(get_db),
):
    """Vertrags-/Abo-Konten fuer die Saganta-Post-Aggregation (Single-Tenant-Trust,
    ueber alle User). notice_within_days: nur Vertraege mit Kuendigungsfrist in N Tagen,
    aufgeloest aus notice_deadline bzw. end_date - notice_period_months (30 Tage/Monat)."""
    stmt = select(Account)
    if only_active:
        stmt = stmt.where(Account.is_active == True)
    accounts = db.execute(stmt.order_by(func.lower(Account.name))).scalars().all()
    today = date.today()
    out = []
    for a in accounts:
        deadline_str = a.notice_deadline
        if not deadline_str and a.end_date and a.notice_period_months:
            try:
                ed = datetime.strptime(a.end_date, "%Y-%m-%d").date()
                deadline_str = (ed - timedelta(days=a.notice_period_months * 30)).isoformat()
            except ValueError:
                deadline_str = None
        days_until = None
        if deadline_str:
            try:
                days_until = (datetime.strptime(deadline_str, "%Y-%m-%d").date() - today).days
            except ValueError:
                deadline_str = None
        if notice_within_days is not None:
            if days_until is None or not (0 <= days_until <= notice_within_days):
                continue
        out.append({
            "id": a.id,
            "name": a.name,
            "kind": a.kind,
            "contract_number": a.contract_number,
            "monthly_amount": float(a.monthly_amount) if a.monthly_amount is not None else None,
            "end_date": a.end_date,
            "notice_period_months": a.notice_period_months,
            "notice_deadline": deadline_str,
            "days_until_notice": days_until,
            "is_active": bool(a.is_active),
        })
    out.sort(key=lambda r: (r["days_until_notice"] is None, r["days_until_notice"] if r["days_until_notice"] is not None else 0))
    return out
