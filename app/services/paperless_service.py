"""Paperless-ngx Forward: Brief als Dokument an Paperless übergeben.

Nutzt den Paperless-Proxy auf node1:8128 (`PAPERLESS_PROXY_URL`) mit
zwei-stufiger Auth: `X-KG-Token` (Knowledge-Gateway-Proxy) und
`Authorization: Token <PAPERLESS_API_TOKEN>` (Paperless selbst).

Endpoint `POST /api/documents/post_document/` ist async: Paperless legt
das Dokument in die Consumer-Queue und liefert eine task-UUID zurück. Die
endgültige `document_id` setzt ein späterer Webhook/Sync (Phase 2.1).
"""
from __future__ import annotations

import os
from typing import Iterable

import httpx

from app.config import settings
from app.models import Letter, LetterFile


class PaperlessForwardError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {
        "X-KG-Token": settings.PAPERLESS_INTEL_KG_TOKEN,
        "Authorization": f"Token {settings.PAPERLESS_API_TOKEN}",
    }


def _primary_file(letter: Letter) -> LetterFile:
    files = sorted(letter.files, key=lambda f: f.page_number or 0)
    if not files:
        raise PaperlessForwardError("letter has no files to forward")
    return files[0]


def forward_letter(
    letter: Letter,
    tag_ids: Iterable[int] | None = None,
    summary: str | None = None,
) -> str:
    """Upload letter file to Paperless. Returns task-UUID."""
    if not settings.PAPERLESS_PROXY_URL or not settings.PAPERLESS_API_TOKEN:
        raise PaperlessForwardError("paperless integration not configured")

    lf = _primary_file(letter)
    path = os.path.join(settings.FILES_DIR, str(letter.user_id), lf.filename)
    if not os.path.exists(path):
        raise PaperlessForwardError(f"file missing on disk: {path}")

    data: dict[str, str | list[int]] = {
        "title": letter.title or lf.original_filename,
    }
    if letter.letter_date:
        data["created"] = letter.letter_date
    if summary:
        # Paperless erlaubt keine direkten Notizen via post_document; wir
        # hängen die Summary an den Titel an, damit sie in Paperless sichtbar
        # bleibt. Tags + Custom-Fields liefen sonst über separate PATCHes.
        data["title"] = f"{data['title']}: {summary[:120]}"

    files_payload: list[tuple[str, tuple[str, bytes, str]]] = []
    with open(path, "rb") as fh:
        files_payload.append(
            ("document", (lf.original_filename or lf.filename, fh.read(), lf.content_type or "application/octet-stream"))
        )

    # Tags als wiederholte Form-Felder
    form_extra: list[tuple[str, str]] = []
    for tid in tag_ids or []:
        form_extra.append(("tags", str(int(tid))))

    try:
        resp = httpx.post(
            f"{settings.PAPERLESS_PROXY_URL}/api/documents/post_document/",
            headers=_headers(),
            data=[*data.items(), *form_extra],
            files=files_payload,
            timeout=60,
        )
    except httpx.HTTPError as exc:
        raise PaperlessForwardError(f"paperless transport error: {exc}") from exc

    if resp.status_code >= 500:
        raise PaperlessForwardError(f"paperless upstream {resp.status_code}: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise PaperlessForwardError(f"paperless rejected {resp.status_code}: {resp.text[:200]}")

    body = resp.text.strip().strip('"')
    if not body:
        raise PaperlessForwardError("paperless returned empty body")
    return body
