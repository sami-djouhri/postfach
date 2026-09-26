"""Account/Vertrags-Routen für Saganta-Document-Engine.

Briefe werden nicht zwingend einem Account zugeordnet: die Verlinkung ist
optional und User-getrieben (UI: Dropdown im Detail-View). Auto-Linking aus
LLM ist Phase 3.1, jetzt nur manuell.
"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Account, Letter, User

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


_ALLOWED = {
    "name", "kind", "contract_number", "monthly_amount",
    "start_date", "end_date", "notice_period_months", "notice_deadline",
    "notes", "is_active", "correspondent_id",
}


def _serialize(a: Account, letter_count: int = 0) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "kind": a.kind,
        "correspondent_id": a.correspondent_id,
        "contract_number": a.contract_number,
        "monthly_amount": float(a.monthly_amount) if a.monthly_amount is not None else None,
        "start_date": a.start_date,
        "end_date": a.end_date,
        "notice_period_months": a.notice_period_months,
        "notice_deadline": a.notice_deadline,
        "notes": a.notes,
        "is_active": bool(a.is_active),
        "letter_count": letter_count,
    }


@router.get("")
def list_accounts(
    only_active: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base = select(Account).where(Account.user_id == user.id)
    if only_active:
        base = base.where(Account.is_active == True)
    accounts = db.execute(base.order_by(func.lower(Account.name))).scalars().all()
    # Letter-Count je Account (deleted ausschließen)
    count_rows = dict(db.execute(
        select(Letter.account_id, func.count(Letter.id))
        .where(Letter.user_id == user.id, Letter.deleted_at.is_(None), Letter.account_id.is_not(None))
        .group_by(Letter.account_id)
    ).all())
    return [_serialize(a, count_rows.get(a.id, 0)) for a in accounts]


@router.get("/{account_id}")
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = db.get(Account, account_id)
    if not a or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="account not found")
    count = db.scalar(
        select(func.count(Letter.id)).where(
            Letter.account_id == account_id, Letter.deleted_at.is_(None),
        )
    ) or 0
    return _serialize(a, count)


@router.post("", status_code=201)
def create_account(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name required")
    unknown = set(payload.keys()) - _ALLOWED
    if unknown:
        raise HTTPException(status_code=400, detail=f"unsupported: {sorted(unknown)}")
    a = Account(user_id=user.id, name=str(payload["name"])[:200])
    for k in _ALLOWED:
        if k in payload and k != "name":
            setattr(a, k, payload[k])
    db.add(a)
    db.commit()
    db.refresh(a)
    return _serialize(a, 0)


@router.patch("/{account_id}")
def patch_account(
    account_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = db.get(Account, account_id)
    if not a or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="account not found")
    unknown = set(payload.keys()) - _ALLOWED
    if unknown:
        raise HTTPException(status_code=400, detail=f"unsupported: {sorted(unknown)}")
    for k, v in payload.items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return _serialize(a)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = db.get(Account, account_id)
    if not a or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="account not found")
    db.delete(a)
    db.commit()


@router.get("/upcoming-notice/days")
def upcoming_notice(
    days: int = Query(90, ge=1, le=730),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Verträge deren Kündigungsfrist in den nächsten N Tagen läuft.
    Aufgelöst aus end_date - notice_period_months."""
    today = date.today()
    horizon = today + timedelta(days=days)
    candidates = db.execute(
        select(Account).where(
            Account.user_id == user.id,
            Account.is_active == True,
        )
    ).scalars().all()
    out = []
    for a in candidates:
        deadline_str = a.notice_deadline
        if not deadline_str and a.end_date and a.notice_period_months:
            try:
                ed = datetime.strptime(a.end_date, "%Y-%m-%d").date()
                # rückwärts in Monaten: vereinfacht 30 Tage/Monat
                deadline = ed - timedelta(days=a.notice_period_months * 30)
                deadline_str = deadline.isoformat()
            except ValueError:
                continue
        if not deadline_str:
            continue
        try:
            dl = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= dl <= horizon:
            row = _serialize(a)
            row["notice_deadline_resolved"] = dl.isoformat()
            row["days_until_notice"] = (dl - today).days
            out.append(row)
    out.sort(key=lambda r: r["days_until_notice"])
    return out
