"""Event-Publisher für den Homelab-Event-Spine.

Schickt mail.ocr_ready-Events an life-ops-api nach erfolgreichem OCR-Pass.
Pattern wie nachrichten event_publisher: best-effort, raised nie.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

LIFE_OPS_EVENTS_URL = os.environ.get("LIFE_OPS_EVENTS_URL", "http://life-ops-api:8000/api/events")
EVENT_TIMEOUT = float(os.environ.get("LIFE_OPS_EVENTS_TIMEOUT", "3.0"))
SOURCE = "briefkasten"


def _post(event: dict[str, Any]) -> bool:
    try:
        with httpx.Client(timeout=EVENT_TIMEOUT) as c:
            r = c.post(LIFE_OPS_EVENTS_URL, json=event)
        if r.status_code in (201, 409):
            return True
        logger.warning("event %s/%s failed: HTTP %s, %s",
                       event.get("source"), event.get("event_type"), r.status_code, r.text[:200])
        return False
    except httpx.HTTPError as e:
        logger.warning("event %s/%s failed: %s", event.get("source"), event.get("event_type"), e)
        return False


def publish_ocr_ready(letter_id: int, title: str | None, text_length: int, page_count: int) -> bool:
    """Emittiert mail.ocr_ready für einen Brief mit fertigem OCR-Text."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary = f"OCR fertig für {title or f'Brief #{letter_id}'}: {text_length} Zeichen aus {page_count} Seite(n)"
    event = {
        "event_type": "mail.ocr_ready",
        "source": SOURCE,
        "external_id": f"letter:{letter_id}:ocr",
        "occurred_at": now,
        "summary": summary[:400],
        "severity": "info",
        "entity_ref": f"letter:{letter_id}",
        "payload": {
            "letter_id": letter_id,
            "title": title,
            "text_length": text_length,
            "page_count": page_count,
        },
    }
    return _post(event)
