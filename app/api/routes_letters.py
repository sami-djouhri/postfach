import asyncio
import logging
import os
import uuid
from datetime import date

import httpx
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.config import settings
from app.db import SessionLocal, get_db
from app.domain import ALLOWED_CONTENT_TYPES, EXTENSION_MAP, LetterCategory, DomainError
from app.models import Letter, LetterFile, User
from app.schemas import (
    LetterCreate,
    LetterFileOut,
    LetterListOut,
    LetterOut,
    LetterUpdate,
    LlmAnalysisResult,
    TagOut,
)
from app.services.kalender_adapter import KalenderAdapter
from app.services.letter_service import LetterService
from app.services.llm_service import LlmService
from app.services.ocr_service import OcrService
from app.services.pdf_service import PdfService

router = APIRouter(prefix="/api/letters", tags=["letters"])
log = logging.getLogger(__name__)

_VISION_SCAN_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _vision_scan(content: bytes, original_filename: str, content_type: str):
    """Foto → entzerrtes Dokument-PDF. In-Process via OpenCV (vision_service),
    optionaler jetson-Fallback wenn VISION_SCAN_URL gesetzt und lokal kein
    Rechteck gefunden wurde."""
    if content_type not in _VISION_SCAN_TYPES:
        return None
    # 1) In-Process OpenCV
    try:
        from app.services.vision_service import crop_document_to_pdf
        pdf = crop_document_to_pdf(content, original_filename)
        if pdf is not None:
            log.info("vision-crop ok (opencv): %s → PDF (%d→%d bytes)",
                     original_filename, len(content), len(pdf))
            return (pdf, "application/pdf")
    except Exception as e:
        log.warning("vision-crop opencv failed (%s): %s", original_filename, e)
    # 2) Fallback: jetson, falls konfiguriert
    if not settings.VISION_SCAN_URL:
        return None
    try:
        resp = httpx.post(
            settings.VISION_SCAN_URL,
            files={"file": (original_filename, content, content_type)},
            timeout=settings.VISION_SCAN_TIMEOUT,
        )
        if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("application/pdf"):
            return None
        return (resp.content, "application/pdf")
    except Exception as e:
        log.warning("vision-scan jetson fallback failed (%s): %s", original_filename, e)
        return None


def _vision_scan_multi(items):
    """Mehrere (content, filename, content_type) zu einem Mehrseiten-PDF kombinieren.
    items: list of (bytes, str, str). Returns (pdf_bytes, "application/pdf") oder None."""
    if not settings.VISION_SCAN_URL or not items:
        return None
    if not all(ct in _VISION_SCAN_TYPES for _, _, ct in items):
        return None
    # /scan-multi liegt auf demselben Service-Root.
    multi_url = settings.VISION_SCAN_URL.rstrip("/").rsplit("/", 1)[0] + "/scan-multi"
    try:
        files_param = [("files", (fn, c, ct)) for c, fn, ct in items]
        resp = httpx.post(multi_url, files=files_param, timeout=settings.VISION_SCAN_TIMEOUT * 2)
        if resp.status_code != 200:
            log.warning("vision-scan-multi HTTP %s: keep originals (%d files)",
                        resp.status_code, len(items))
            return None
        if not resp.headers.get("content-type", "").startswith("application/pdf"):
            return None
        log.info("vision-scan-multi ok: %d pages → PDF (%d bytes)", len(items), len(resp.content))
        return (resp.content, "application/pdf")
    except Exception as e:
        log.warning("vision-scan-multi failed: %s, keep originals", e)
        return None


_VALID_CATEGORIES = {c.value for c in LetterCategory}



_DEFAULT_TITLE_PATTERNS = (
    "Brief vom ",
    "Upload ",
    "upload",
    "Scan vom ",
    "Quick-Scan",
)


def _is_default_title(title: str | None) -> bool:
    if not title:
        return True
    t = title.strip()
    return any(t.startswith(p) for p in _DEFAULT_TITLE_PATTERNS) or t.lower().endswith((".jpg", ".jpeg", ".png", ".pdf", ".webp"))


def _apply_llm_result(letter: Letter, result: LlmAnalysisResult) -> None:
    """Übernimmt absender/kategorie/zusammenfassung in den Letter, wenn das LLM-Result
    plausible Werte liefert. Wird sowohl von analyze_letter (Vordergrund) als auch
    von _quick_scan_background genutzt."""
    if result.absender and not letter.sender:
        letter.sender = result.absender[:200]
    # Correspondent verlinken (idempotent get_or_create)
    if letter.sender and letter.correspondent_id is None:
        try:
            from app.services import correspondent_service
            from sqlalchemy.orm import object_session
            sess = object_session(letter)
            if sess is not None:
                correspondent_service.attach_to_letter(sess, letter, letter.sender)
        except Exception as e:
            log.warning("correspondent attach failed for letter %s: %s", letter.id, e)
    if result.kategorie and result.kategorie in _VALID_CATEGORIES:
        letter.category = result.kategorie
    if result.zusammenfassung:
        letter.llm_summary = result.zusammenfassung
    # Auto-Titel wenn aktueller Titel generisch ("Brief vom YYYY-MM-DD", "Upload …", Filename)
    if _is_default_title(letter.title):
        cand = (result.titel or "").strip()
        if not cand and result.zusammenfassung:
            cand = result.zusammenfassung.split(".")[0].strip()
        cand = " ".join(cand.split())[:80]
        if cand:
            letter.title = cand


def _post_upload_background(letter_id: int, user_id: int) -> None:
    """Auto-Pipeline nach normalem Upload: OCR (wenn nicht done) + LLM (wenn kein summary).

    Idempotent: läuft die OCR durch und das ocr_text ist da, wird via
    _quick_scan_background die LLM-Analyse + Kalender-Push gemacht."""
    db = SessionLocal()
    try:
        letter = db.query(Letter).filter_by(id=letter_id, user_id=user_id).first()
        if letter is None:
            return
        # OCR wenn nötig
        if letter.ocr_status != "done" and letter.files:
            try:
                OcrService(db).run_ocr(letter_id, user_id)
                db.refresh(letter)
            except Exception as e:
                log.warning("auto-pipeline ocr fail letter %s: %s", letter_id, e)
                letter.ocr_status = "error"
                db.commit()
                return
        # LLM wenn ocr_text da und keine Analyse vorhanden
        if letter.ocr_text and letter.analysis_status not in ("done", "processing"):
            letter.analysis_status = "processing"
            db.commit()
    finally:
        db.close()
    # Delegiere an _quick_scan_background: eigene Session, eigener Loop
    _quick_scan_background(letter_id, user_id)
    # Status final setzen + Semantic-Index
    db = SessionLocal()
    try:
        letter = db.query(Letter).filter_by(id=letter_id, user_id=user_id).first()
        if letter is not None:
            letter.analysis_status = "done" if letter.llm_summary else "error"
            db.commit()
            if letter.ocr_text:
                try:
                    from app.services import semantic_service
                    semantic_service.index_letter(db, letter)
                except Exception as e:
                    log.warning("semantic index post-upload failed for %s: %s", letter_id, e)
    finally:
        db.close()


def _quick_scan_background(letter_id: int, user_id: int) -> None:
    """LLM-Analyse + Kalender-Sync nach quick_scan. Eigene DB-Session, eigener Event-Loop."""
    db = SessionLocal()
    try:
        letter = db.query(Letter).filter_by(id=letter_id, user_id=user_id).first()
        if letter is None or not letter.ocr_text:
            log.warning("quick-scan bg: letter %s nicht analysierbar (fehlt/kein OCR)", letter_id)
            return
        llm_svc = LlmService()
        result = asyncio.run(llm_svc.analyze(letter.ocr_text))
        if result.error:
            log.warning("quick-scan bg: LLM-Fehler letter %s: %s", letter_id, result.error)
            return
        _apply_llm_result(letter, result)
        db.commit()
        log.info("quick-scan bg: letter %s analysiert (sender=%r, cat=%r)",
                 letter_id, letter.sender, letter.category)

        # Kalender-Push fire-and-forget (Fehler in log, nicht weiterreichen)
        if result.fristen:
            kalender = KalenderAdapter()
            for frist in result.fristen:
                try:
                    asyncio.run(kalender.push_deadline(
                        typ=frist.typ, datum=frist.datum,
                        beschreibung=frist.beschreibung, letter_id=letter_id,
                    ))
                except Exception as e:
                    log.warning("quick-scan bg: kalender push fehlgeschlagen: %s", e)
    finally:
        db.close()


def _file_out(f: LetterFile) -> LetterFileOut:
    return LetterFileOut(
        id=f.id,
        filename=f.filename,
        original_filename=f.original_filename,
        content_type=f.content_type,
        file_size=f.file_size,
        page_number=f.page_number,
        ocr_text=f.ocr_text,
        created_at=f.created_at,
    )


def _tag_out(t) -> TagOut:
    return TagOut(id=t.id, name=t.name, color=t.color)


def _letter_out(l: Letter) -> LetterOut:
    return LetterOut(
        id=l.id,
        title=l.title,
        sender=l.sender,
        category=l.category,
        received_date=l.received_date,
        letter_date=l.letter_date,
        ocr_text=l.ocr_text,
        ocr_status=l.ocr_status,
        analysis_status=l.analysis_status,
        llm_summary=l.llm_summary,
        notes=l.notes,
        is_archived=l.is_archived,
        snoozed_until=l.snoozed_until,
        paperless_id=l.paperless_id,
        created_at=l.created_at,
        updated_at=l.updated_at,
        files=[_file_out(f) for f in l.files],
        tags=[_tag_out(t) for t in l.tags],
    )


def _letter_list_out(l: Letter, file_count: int) -> LetterListOut:
    return LetterListOut(
        id=l.id,
        title=l.title,
        sender=l.sender,
        category=l.category,
        received_date=l.received_date,
        ocr_status=l.ocr_status,
        analysis_status=l.analysis_status,
        is_archived=l.is_archived,
        snoozed_until=l.snoozed_until,
        paperless_id=l.paperless_id,
        created_at=l.created_at,
        file_count=file_count,
        tags=[_tag_out(t) for t in l.tags],
    )




@router.get("/senders")
def list_senders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Distinct nicht-leere Absender für Filter-Dropdown: sortiert alphabetisch."""
    from sqlalchemy import select, func as sa_func
    rows = db.execute(
        select(Letter.sender)
        .where(Letter.user_id == user.id,
               Letter.deleted_at.is_(None),
               Letter.sender.isnot(None),
               Letter.sender != "")
        .distinct()
        .order_by(sa_func.lower(Letter.sender))
    ).scalars().all()
    return [s for s in rows if s]

@router.get("", response_model=list[LetterListOut])
def list_letters(
    category: str | None = None,
    is_archived: bool | None = None,
    search: str | None = None,
    tag_id: int | None = None,
    sender_in: str | None = Query(None, description="Komma-Liste exakter Absender"),
    letter_date_from: str | None = Query(None, description="YYYY-MM-DD inklusiv"),
    letter_date_to: str | None = Query(None, description="YYYY-MM-DD inklusiv"),
    tag_ids_all: str | None = Query(None, description="Komma-Liste tag-IDs: alle müssen am Brief sein"),
    include_snoozed: bool = False,
    show_deleted: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    senders_list = [s.strip() for s in (sender_in or "").split(",") if s.strip()] or None
    tag_ids_all_list = [int(t) for t in (tag_ids_all or "").split(",") if t.strip().isdigit()] or None
    svc = LetterService(db)
    items = svc.list_all(
        user_id=user.id, category=category, is_archived=is_archived,
        search=search, tag_id=tag_id, skip=skip, limit=limit,
        include_snoozed=include_snoozed, show_deleted=show_deleted,
        senders=senders_list, letter_date_from=letter_date_from,
        letter_date_to=letter_date_to, tag_ids_all=tag_ids_all_list,
    )
    return [_letter_list_out(item["letter"], item["file_count"]) for item in items]


@router.post("", response_model=LetterOut, status_code=201)
def create_letter(
    body: LetterCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    letter = svc.create(
        user_id=user.id,
        title=body.title,
        sender=body.sender,
        category=body.category,
        received_date=body.received_date,
        letter_date=body.letter_date,
        notes=body.notes,
        tag_ids=body.tag_ids,
    )
    return _letter_out(letter)


@router.get("/{letter_id}", response_model=LetterOut)
def get_letter(
    letter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    letter = svc.get(letter_id, user.id)
    return _letter_out(letter)


@router.put("/{letter_id}", response_model=LetterOut)
def update_letter(
    letter_id: int,
    body: LetterUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    update_data = body.model_dump(exclude_unset=True)
    letter = svc.update(letter_id, user.id, **update_data)
    return _letter_out(letter)


@router.delete("/{letter_id}", status_code=204)
def delete_letter(
    letter_id: int,
    hard: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    if hard:
        svc.hard_delete(letter_id, user.id)
    else:
        svc.delete(letter_id, user.id)


@router.post("/{letter_id}/restore", response_model=LetterOut)
def restore_letter(
    letter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    letter = svc.restore(letter_id, user.id)
    return _letter_out(letter)


@router.post("/{letter_id}/files", response_model=LetterFileOut, status_code=201)
def upload_file(
    letter_id: int,
    file: UploadFile = File(...),
    background: BackgroundTasks = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    letter = svc.get(letter_id, user.id)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise DomainError(
            f"Dateityp '{file.content_type}' nicht erlaubt. "
            "Erlaubt: JPEG, PNG, WebP, PDF"
        )

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise DomainError("Datei zu gross (max. 20 MB)")

    effective_content_type = file.content_type
    scanned = _vision_scan(content, file.filename or "upload", file.content_type)
    if scanned is not None:
        content, effective_content_type = scanned

    ext = EXTENSION_MAP.get(effective_content_type, ".bin")
    filename = f"{letter_id}_{uuid.uuid4().hex}{ext}"

    user_dir = os.path.join(settings.FILES_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    page_number = len(letter.files) + 1

    letter_file = LetterFile(
        letter_id=letter_id,
        filename=filename,
        original_filename=file.filename or "upload",
        content_type=effective_content_type,
        file_size=len(content),
        page_number=page_number,
    )
    db.add(letter_file)

    # Reset OCR status if files change: Pipeline läuft danach automatisch.
    if letter.ocr_status == "done":
        letter.ocr_status = "pending"
    letter.analysis_status = "processing"

    db.commit()
    db.refresh(letter_file)
    if background is not None:
        background.add_task(_post_upload_background, letter_id, user.id)
    return _file_out(letter_file)


@router.get("/{letter_id}/files/{file_id}")
def get_file(
    letter_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    letter_file = svc.get_file(letter_id, file_id, user.id)
    file_path = os.path.join(settings.FILES_DIR, str(user.id), letter_file.filename)
    if not os.path.exists(file_path):
        raise DomainError("Datei nicht gefunden auf dem Server")
    return FileResponse(
        file_path,
        media_type=letter_file.content_type,
        filename=letter_file.original_filename,
    )


@router.delete("/{letter_id}/files/{file_id}", status_code=204)
def delete_file(
    letter_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = LetterService(db)
    svc.delete_file(letter_id, file_id, user.id)


@router.post("/{letter_id}/ocr", response_model=LetterOut)
def run_ocr(
    letter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = OcrService(db)
    letter = svc.run_ocr(letter_id, user.id)
    return _letter_out(letter)


@router.post("/{letter_id}/analyze", response_model=LlmAnalysisResult)
async def analyze_letter(
    letter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    letter_svc = LetterService(db)
    letter = letter_svc.get(letter_id, user.id)

    if not letter.ocr_text:
        raise DomainError("Kein OCR-Text vorhanden. Bitte zuerst OCR ausfuehren.")

    llm_svc = LlmService()
    result = await llm_svc.analyze(letter.ocr_text)

    if not result.error:
        _apply_llm_result(letter, result)
        letter.analysis_status = "done"
        db.commit()
        if letter.ocr_text:
            try:
                from app.services import semantic_service
                semantic_service.index_letter(db, letter)
            except Exception as e:
                log.warning("semantic index post-analyze failed for %s: %s", letter_id, e)
    else:
        letter.analysis_status = "error"
        db.commit()

    # Push fristen to Kalender (fire-and-forget, errors logged but not blocking)
    if result.fristen:
        kalender = KalenderAdapter()
        synced = 0
        skipped = 0
        errors: list[str] = []
        for frist in result.fristen:
            sync_result = await kalender.push_deadline(
                typ=frist.typ,
                datum=frist.datum,
                beschreibung=frist.beschreibung,
                letter_id=letter_id,
            )
            if sync_result.ok:
                synced += 1
            elif sync_result.status == "skipped":
                skipped += 1
            else:
                errors.append(sync_result.message or "Kalender-Sync fehlgeschlagen")
        result.calendar_synced = synced
        result.calendar_skipped = skipped
        result.calendar_errors = errors

    return result


@router.get("/{letter_id}/pdf")
def export_pdf(
    letter_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    letter_svc = LetterService(db)
    letter = letter_svc.get(letter_id, user.id)

    pdf_svc = PdfService()
    pdf_bytes = pdf_svc.generate(letter, user.id)

    safe_title = "".join(c for c in letter.title if c.isalnum() or c in " -_")[:50]
    filename = f"Brief_{safe_title}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/quick-scan", response_model=LetterOut, status_code=201)
def quick_scan(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Query("", description="Optionaler Titel; sonst 'Brief vom YYYY-MM-DD'"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mobile-First-Pfad: ein Foto → fertig analysierter Brief.

    Pipeline: Letter anlegen → Vision-Scan (Foto→PDF) → Datei speichern → OCR synchron →
    LLM-Analyse als Background-Task (kann 60–90 s dauern). Antwort enthält Letter mit
    OCR-Text; sender/category/llm_summary werden vom Background-Task nachgereicht.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise DomainError(
            f"Dateityp '{file.content_type}' nicht erlaubt. Erlaubt: JPEG, PNG, WebP, PDF"
        )

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise DomainError("Datei zu gross (max. 20 MB)")

    # Letter mit Default-Titel anlegen
    svc = LetterService(db)
    letter_title = title or f"Brief vom {date.today().isoformat()}"
    letter = svc.create(
        user_id=user.id,
        title=letter_title,
        sender=None,
        category=None,
        received_date=date.today().isoformat(),
        letter_date=None,
        notes=None,
        tag_ids=[],
    )

    # Vision-Scan + File speichern (deckt sich mit upload_file)
    effective_content_type = file.content_type
    scanned = _vision_scan(content, file.filename or "upload", file.content_type)
    if scanned is not None:
        content, effective_content_type = scanned

    ext = EXTENSION_MAP.get(effective_content_type, ".bin")
    filename = f"{letter.id}_{uuid.uuid4().hex}{ext}"
    user_dir = os.path.join(settings.FILES_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    letter_file = LetterFile(
        letter_id=letter.id,
        filename=filename,
        original_filename=file.filename or "upload",
        content_type=effective_content_type,
        file_size=len(content),
        page_number=1,
    )
    db.add(letter_file)
    db.commit()

    # OCR synchron (Tesseract ~2-5 s pro Seite)
    ocr_svc = OcrService(db)
    letter = ocr_svc.run_ocr(letter.id, user.id)

    # LLM-Analyse im Hintergrund (60-90 s); Felder werden in der DB ergänzt
    background.add_task(_quick_scan_background, letter.id, user.id)

    return _letter_out(letter)


@router.post("/quick-scan-multi", response_model=LetterOut, status_code=201)
def quick_scan_multi(
    background: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Mehrere Foto-Seiten in gewünschter Reihenfolge"),
    title: str = Query("", description="Optionaler Titel; sonst 'Brief vom YYYY-MM-DD'"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mobile-First für mehrseitige Briefe: n Fotos → ein Mehrseiten-PDF → 1 Letter mit OCR + LLM.

    Wenn alle Uploads Bilder sind und VISION_SCAN_URL gesetzt: jetson /scan-multi macht ein
    kombiniertes PDF. Sonst werden die Originale als separate Letter-Files gespeichert.
    """
    if not files:
        raise DomainError("Mindestens eine Datei nötig")
    if len(files) > 30:
        raise DomainError("Maximal 30 Seiten pro Aufruf")

    # Validate + read all
    items = []  # (content, filename, content_type)
    for f in files:
        if f.content_type not in ALLOWED_CONTENT_TYPES:
            raise DomainError(
                f"Dateityp '{f.content_type}' nicht erlaubt. Erlaubt: JPEG, PNG, WebP, PDF"
            )
        c = f.file.read()
        if len(c) > settings.MAX_UPLOAD_SIZE:
            raise DomainError(f"{f.filename or 'upload'} ist zu gross (max. 20 MB)")
        items.append((c, f.filename or "upload", f.content_type))

    # Wenn alles Bilder sind und VISION_SCAN_URL gesetzt → ein gemeinsames Mehrseiten-PDF.
    all_images = all(ct in _VISION_SCAN_TYPES for _, _, ct in items)
    if all_images and len(items) > 1:
        scanned = _vision_scan_multi(items)
        if scanned is not None:
            items = [(scanned[0], "scan-multi.pdf", scanned[1])]
    elif all_images and len(items) == 1:
        scanned = _vision_scan(items[0][0], items[0][1], items[0][2])
        if scanned is not None:
            items = [(scanned[0], items[0][1], scanned[1])]
    # Sonst: gemischter Inhalt oder Vision-Scan disabled → Originale separat behalten

    # Letter anlegen
    svc = LetterService(db)
    letter_title = title or f"Brief vom {date.today().isoformat()}"
    letter = svc.create(
        user_id=user.id,
        title=letter_title,
        sender=None,
        category=None,
        received_date=date.today().isoformat(),
        letter_date=None,
        notes=None,
        tag_ids=[],
    )

    # Alle Items als LetterFiles speichern
    user_dir = os.path.join(settings.FILES_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    for page_num, (content, original_fn, ct) in enumerate(items, start=1):
        ext = EXTENSION_MAP.get(ct, ".bin")
        fn = f"{letter.id}_{uuid.uuid4().hex}{ext}"
        with open(os.path.join(user_dir, fn), "wb") as fh:
            fh.write(content)
        db.add(LetterFile(
            letter_id=letter.id,
            filename=fn,
            original_filename=original_fn,
            content_type=ct,
            file_size=len(content),
            page_number=page_num,
        ))
    db.commit()

    # OCR synchron über alle Files
    ocr_svc = OcrService(db)
    letter = ocr_svc.run_ocr(letter.id, user.id)

    background.add_task(_quick_scan_background, letter.id, user.id)
    return _letter_out(letter)


_AUDIO_CONTENT_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mpeg",  # mp3
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
}

_AUDIO_EXTENSION_MAP = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
}


@router.post("/voice-memo", response_model=LetterOut, status_code=201)
def voice_memo(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Query("", description="Optionaler Titel; sonst 'Sprachnotiz vom YYYY-MM-DD'"),
    language: str = Query("de", description="Sprach-Hint für STT (de/en/auto)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sprachnotiz → Letter. Audio → ai-stt (faster-whisper) → Transcript als
    ocr_text → LLM-Analyse als Background-Task. Original-Audio wird als
    LetterFile gespeichert.
    """
    if not settings.STT_URL:
        raise HTTPException(status_code=503, detail="STT_URL nicht konfiguriert")
    if file.content_type not in _AUDIO_CONTENT_TYPES:
        raise DomainError(
            f"Dateityp '{file.content_type}' nicht erlaubt. "
            f"Erlaubt: webm, ogg, mp3, m4a, wav"
        )

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise DomainError("Audio zu gross (max. 20 MB)")
    if not content:
        raise DomainError("Audio-Datei ist leer")

    # Transcribe via ai-stt
    try:
        with httpx.Client(timeout=120.0) as client:
            files = {"file": (file.filename or "memo.webm", content, file.content_type)}
            data = {"language": language} if language and language != "auto" else {}
            r = client.post(f"{settings.STT_URL.rstrip('/')}/api/stt", files=files, data=data)
            r.raise_for_status()
            stt = r.json()
    except httpx.HTTPError as exc:
        log.warning("voice-memo: STT-Fehler: %s", exc)
        raise HTTPException(status_code=502, detail=f"STT-Service nicht erreichbar: {exc}")
    except Exception as exc:
        log.exception("voice-memo: STT unerwartet")
        raise HTTPException(status_code=500, detail=str(exc))

    transcript = (stt.get("text") or "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="STT lieferte leeren Text")

    # Letter mit Transcript als ocr_text anlegen
    svc = LetterService(db)
    letter_title = title or f"Sprachnotiz vom {date.today().isoformat()}"
    letter = svc.create(
        user_id=user.id,
        title=letter_title,
        sender=None,
        category="Notiz",
        received_date=date.today().isoformat(),
        letter_date=None,
        notes=None,
        tag_ids=[],
    )
    letter.ocr_text = transcript
    letter.ocr_status = "completed"
    db.commit()

    # Original-Audio als LetterFile speichern
    ext = _AUDIO_EXTENSION_MAP.get(file.content_type, ".bin")
    filename = f"{letter.id}_{uuid.uuid4().hex}{ext}"
    user_dir = os.path.join(settings.FILES_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    with open(os.path.join(user_dir, filename), "wb") as fh:
        fh.write(content)
    db.add(LetterFile(
        letter_id=letter.id,
        filename=filename,
        original_filename=file.filename or "memo.webm",
        content_type=file.content_type,
        file_size=len(content),
        page_number=1,
        ocr_text=transcript,
    ))
    db.commit()
    db.refresh(letter)

    # LLM-Analyse im Hintergrund (gleiche Pipeline wie quick-scan)
    background.add_task(_quick_scan_background, letter.id, user.id)
    return _letter_out(letter)


@router.post("/{letter_id}/forward-to-paperless")
def forward_to_paperless(
    letter_id: int,
    body: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.services.paperless_service import PaperlessForwardError, forward_letter

    svc = LetterService(db)
    letter = svc.get(letter_id, user.id)
    if letter.paperless_id:
        raise HTTPException(
            status_code=409,
            detail={"reason": "already forwarded", "paperless_id": letter.paperless_id},
        )
    tag_ids = body.get("tag_ids") or []
    summary = body.get("summary")
    if not isinstance(tag_ids, list):
        raise HTTPException(status_code=400, detail="tag_ids must be a list")
    try:
        task_id = forward_letter(letter, tag_ids=tag_ids, summary=summary)
    except PaperlessForwardError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    letter.paperless_id = task_id
    db.commit()
    db.refresh(letter)
    return {"paperless_task_id": task_id, "letter_id": letter.id}


@router.post("/bulk", status_code=202)
def bulk_upload(
    background: BackgroundTasks,
    files: list[UploadFile] = File(..., description="N Dateien: pro File entsteht ein eigener Letter"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk-Upload: pro File ein eigener Letter, gesamte Pipeline (Vision-Scan,
    OCR, LLM, Kalender) läuft im Hintergrund. Response sofort mit den
    Letter-IDs; Client pollt `GET /letters/{id}` bis `analysis_status=done`.
    """
    if not files:
        raise DomainError("Mindestens eine Datei nötig")
    if len(files) > 50:
        raise DomainError("Maximal 50 Dateien pro Bulk-Aufruf")

    svc = LetterService(db)
    user_dir = os.path.join(settings.FILES_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    created: list[dict] = []
    today = date.today().isoformat()

    for upload in files:
        if upload.content_type not in ALLOWED_CONTENT_TYPES:
            # Sammeln statt abbrechen: User soll sehen, was fehlschlug.
            created.append({"original_filename": upload.filename or "upload", "error": f"Dateityp {upload.content_type} nicht erlaubt"})
            continue
        content = upload.file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            created.append({"original_filename": upload.filename or "upload", "error": "Zu groß (max. 20 MB)"})
            continue

        # Vision-Scan (best-effort, sync): bei Image-Upload Crop+PDF.
        effective_content_type = upload.content_type
        scanned = _vision_scan(content, upload.filename or "upload", upload.content_type)
        if scanned is not None:
            content, effective_content_type = scanned

        # Letter mit Placeholder-Titel; LLM überschreibt später automatisch.
        letter = svc.create(
            user_id=user.id,
            title=f"Brief vom {today}",
            sender=None,
            category=None,
            received_date=today,
            letter_date=None,
            notes=None,
            tag_ids=[],
        )

        ext = EXTENSION_MAP.get(effective_content_type, ".bin")
        fn = f"{letter.id}_{uuid.uuid4().hex}{ext}"
        with open(os.path.join(user_dir, fn), "wb") as fh:
            fh.write(content)
        db.add(LetterFile(
            letter_id=letter.id,
            filename=fn,
            original_filename=upload.filename or "upload",
            content_type=effective_content_type,
            file_size=len(content),
            page_number=1,
        ))
        # Pipeline-Status: sofort 'processing', Worker setzt 'done'.
        letter.analysis_status = "processing"
        letter.ocr_status = "pending"
        db.commit()
        background.add_task(_post_upload_background, letter.id, user.id)
        created.append({
            "letter_id": letter.id,
            "original_filename": upload.filename or "upload",
            "title": letter.title,
        })

    return {"letters": created}

@router.get("/semantic-search", response_model=list[LetterListOut])
def semantic_search(
    q: str = Query(min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """k-NN-Suche über die Embedding-Repräsentation der Briefe. Snippet-/
    Rank-Order folgt der Vector-Distance (niedriger = ähnlicher)."""
    from app.services import semantic_service
    try:
        hits = semantic_service.search(db, user.id, q, limit=limit)
    except Exception as e:
        log.warning("semantic-search failed: %s", e)
        return []
    if not hits:
        return []
    id_order = {lid: i for i, (lid, _) in enumerate(hits)}
    stmt = (
        select(Letter)
        .where(Letter.id.in_(id_order.keys()), Letter.user_id == user.id, Letter.deleted_at.is_(None))
        .options(joinedload(Letter.tags), joinedload(Letter.files))
    )
    letters = db.execute(stmt).unique().scalars().all()
    letters.sort(key=lambda l: id_order.get(l.id, 1 << 30))
    return [_letter_list_out(l, len(l.files)) for l in letters]
