"""Paperless-ngx → Briefkasten Migration.

Zieht alle Dokumente aus Paperless-ngx (node1:8128) in den Briefkasten-Store,
mappt Correspondents + Tags, importiert PDFs als LetterFile + OCR-Text als
Letter.ocr_text. Idempotent über `paperless_import_map`: wiederholte Läufe
springen bereits importierte Documents.

Usage (im Container):
    docker exec briefkasten python /app/scripts/migrate-from-paperless.py --dry-run
    docker exec briefkasten python /app/scripts/migrate-from-paperless.py --apply --user-id 1

Pflicht-Env: PAPERLESS_URL (z.B. http://192.0.2.10:8128), PAPERLESS_API_TOKEN.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

# Pfad-Setup: Script wird in /app/scripts/ erwartet, App-Code in /app/app/.
sys.path.insert(0, "/app")
from app.db import SessionLocal  # type: ignore
from app.models import Correspondent, Letter, LetterFile, Tag  # type: ignore

PAGE_SIZE = 50
FILE_DIR = Path("/app/data/files")


def normalize(name: str) -> str:
    return " ".join(name.lower().split())


def get_or_create_correspondent(db: Session, user_id: int, name: str) -> Correspondent | None:
    if not name:
        return None
    norm = normalize(name)
    found = db.execute(
        select(Correspondent).where(
            Correspondent.user_id == user_id, Correspondent.normalized == norm
        )
    ).scalar_one_or_none()
    if found:
        return found
    c = Correspondent(user_id=user_id, name=name, normalized=norm)
    db.add(c)
    db.flush()
    return c


def get_or_create_tag(db: Session, user_id: int, name: str) -> Tag | None:
    if not name:
        return None
    found = db.execute(
        select(Tag).where(Tag.user_id == user_id, Tag.name == name)
    ).scalar_one_or_none()
    if found:
        return found
    t = Tag(user_id=user_id, name=name)
    db.add(t)
    db.flush()
    return t


def already_imported(db: Session, paperless_doc_id: int) -> int | None:
    row = db.execute(
        text("SELECT letter_id FROM paperless_import_map WHERE paperless_doc_id = :id"),
        {"id": paperless_doc_id},
    ).first()
    return row[0] if row else None


def record_import(
    db: Session,
    paperless_doc_id: int,
    letter_id: int,
    source_url: str,
    checksum: str,
) -> None:
    db.execute(
        text(
            "INSERT INTO paperless_import_map "
            "(paperless_doc_id, letter_id, source_url, checksum) "
            "VALUES (:p, :l, :s, :c)"
        ),
        {"p": paperless_doc_id, "l": letter_id, "s": source_url, "c": checksum},
    )


def fetch_paperless_pages(client: httpx.Client, base: str) -> Iterable[dict[str, Any]]:
    url: str | None = f"{base}/api/documents/?page_size={PAGE_SIZE}&ordering=id"
    while url:
        r = client.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()
        for doc in data.get("results", []):
            yield doc
        url = data.get("next")


def fetch_lookup(client: httpx.Client, base: str, path: str) -> dict[int, str]:
    out: dict[int, str] = {}
    url: str | None = f"{base}/api/{path}/?page_size=200"
    while url:
        r = client.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        for item in data.get("results", []):
            out[item["id"]] = item.get("name", "")
        url = data.get("next")
    return out


def download_file(
    client: httpx.Client, base: str, doc_id: int, suffix: str = ".pdf"
) -> tuple[bytes, str]:
    r = client.get(f"{base}/api/documents/{doc_id}/download/", timeout=120)
    r.raise_for_status()
    blob = r.content
    return blob, hashlib.sha256(blob).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Echtlauf. Default: dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="0 = alle")
    args = parser.parse_args()
    apply = args.apply and not args.dry_run

    base = os.environ.get("PAPERLESS_URL", "").rstrip("/")
    token = os.environ.get("PAPERLESS_API_TOKEN", "")
    if not base or not token:
        print("ERROR: PAPERLESS_URL + PAPERLESS_API_TOKEN müssen gesetzt sein.")
        return 2

    headers = {"Authorization": f"Token {token}"}
    client = httpx.Client(headers=headers, follow_redirects=True)

    print(f"→ Paperless: {base}")
    r = client.get(f"{base}/api/documents/?page_size=1", timeout=30)
    r.raise_for_status()
    total = r.json().get("count", 0)
    print(f"→ Total documents: {total}")

    correspondents_map = fetch_lookup(client, base, "correspondents")
    tags_map = fetch_lookup(client, base, "tags")
    print(f"→ {len(correspondents_map)} Correspondents, {len(tags_map)} Tags")

    if apply:
        FILE_DIR.mkdir(parents=True, exist_ok=True)

    imported = skipped = errors = 0
    with SessionLocal() as db:
        for doc in fetch_paperless_pages(client, base):
            if args.limit and imported >= args.limit:
                break
            doc_id = doc["id"]
            existing = already_imported(db, doc_id)
            if existing:
                skipped += 1
                continue
            title = doc.get("title") or f"Paperless #{doc_id}"
            correspondent_name = correspondents_map.get(doc.get("correspondent") or 0, "")
            tag_names = [tags_map.get(t, "") for t in doc.get("tags") or [] if tags_map.get(t)]
            created = doc.get("created") or doc.get("added")
            received_date = (created or "")[:10] or None
            ocr_text = doc.get("content") or None

            print(f"  [{doc_id}] {title}: {correspondent_name or '–'} ({len(tag_names)} tags)")
            if not apply:
                imported += 1
                continue

            try:
                blob, checksum = download_file(client, base, doc_id)
            except Exception as e:
                errors += 1
                print(f"    ! Download fail: {e}")
                continue

            corresp = get_or_create_correspondent(db, args.user_id, correspondent_name)
            letter = Letter(
                user_id=args.user_id,
                title=title,
                sender=correspondent_name or None,
                received_date=received_date,
                ocr_text=ocr_text,
                ocr_status="completed" if ocr_text else "pending",
                analysis_status="none",
                correspondent_id=corresp.id if corresp else None,
                paperless_id=str(doc_id),
            )
            db.add(letter)
            db.flush()

            for tn in tag_names:
                tag = get_or_create_tag(db, args.user_id, tn)
                if tag and tag not in letter.tags:
                    letter.tags.append(tag)

            fname = f"paperless-{doc_id}-{uuid.uuid4().hex[:8]}.pdf"
            fpath = FILE_DIR / fname
            fpath.write_bytes(blob)
            db.add(
                LetterFile(
                    letter_id=letter.id,
                    filename=fname,
                    original_filename=f"paperless-{doc_id}.pdf",
                    content_type="application/pdf",
                    file_size=len(blob),
                    page_number=1,
                    ocr_text=ocr_text,
                )
            )
            record_import(
                db,
                paperless_doc_id=doc_id,
                letter_id=letter.id,
                source_url=f"{base}/documents/{doc_id}/",
                checksum=checksum,
            )
            db.commit()
            imported += 1

    print(
        f"\n→ Done. imported={imported} skipped={skipped} errors={errors} "
        f"mode={'apply' if apply else 'dry-run'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
