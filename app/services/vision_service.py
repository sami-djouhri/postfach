"""In-Process Vision-Crop: Foto → begradigtes Dokument-PDF via OpenCV.

Ersetzt den jetson-basierten `_vision_scan` (`VISION_SCAN_URL`) als
Default-Pfad. Heuristik:
1. Bild laden, auf max. 1600 px verkleinern für schnelle Edge-Detection.
2. Graustufen → Gauss-Blur → Canny.
3. Größte konvexe 4-Eck-Kontur finden (mind. 25 % der Bildfläche).
4. Perspektive auf rechtwinkligen Output warpen.
5. Reportlab/PIL PDF mit dem gecroppten Bild.

Fallback bei Misserfolg: `None` → Caller behält Original.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)

_MAX_DIM = 1600
_MIN_AREA_RATIO = 0.20  # gecroppte Fläche muss mind. 20 % des Bildes ausmachen


def _order_corners(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()
    return np.array([
        pts[np.argmin(s)],   # top-left
        pts[np.argmin(d)],   # top-right
        pts[np.argmax(s)],   # bottom-right
        pts[np.argmax(d)],   # bottom-left
    ], dtype=np.float32)


def _detect_doc_corners(gray: np.ndarray) -> Optional[np.ndarray]:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 180)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    img_area = gray.shape[0] * gray.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        if cv2.contourArea(approx) < _MIN_AREA_RATIO * img_area:
            break  # alle weiteren sind kleiner
        return approx.reshape(4, 2)
    return None


def _warp_to_rect(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    ordered = _order_corners(corners)
    (tl, tr, br, bl) = ordered
    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)
    width = int(max(w_top, w_bot))
    height = int(max(h_left, h_right))
    if width < 100 or height < 100:
        raise ValueError("warped output too small")
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(img, M, (width, height))


def _to_pdf_bytes(rgb_array: np.ndarray) -> bytes:
    pil = Image.fromarray(rgb_array)
    buf = io.BytesIO()
    # PIL kann direkt zu PDF speichern (single page)
    pil.save(buf, format="PDF", resolution=300.0)
    return buf.getvalue()


def crop_document_to_pdf(image_bytes: bytes, filename: str = "upload") -> Optional[bytes]:
    """Foto entzerren → PDF-Bytes. None wenn kein Dokument-Rechteck gefunden."""
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            logger.info("vision: cv2 konnte %s nicht dekodieren", filename)
            return None
        h, w = bgr.shape[:2]
        scale = min(_MAX_DIM / max(h, w), 1.0)
        if scale < 1.0:
            small = cv2.resize(bgr, (int(w * scale), int(h * scale)))
        else:
            small = bgr
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        corners = _detect_doc_corners(gray)
        if corners is None:
            logger.info("vision: kein 4-Eck in %s, fallback", filename)
            return None
        # zurück auf Originalauflösung skalieren
        if scale < 1.0:
            corners = corners / scale
        warped = _warp_to_rect(bgr, corners.astype(np.float32))
        # Helligkeit/Kontrast normalisieren (CLAHE auf L-Kanal)
        lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        bgr_norm = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        rgb = cv2.cvtColor(bgr_norm, cv2.COLOR_BGR2RGB)
        return _to_pdf_bytes(rgb)
    except Exception as e:
        logger.warning("vision-crop failed for %s: %s", filename, e)
        return None
