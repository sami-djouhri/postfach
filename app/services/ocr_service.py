import logging
import os
import subprocess
import tempfile

from PIL import Image
import pytesseract
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import DomainError
from app.models import Letter, LetterFile
from app.services import event_publisher

logger = logging.getLogger(__name__)


class OcrService:
    def __init__(self, db: Session):
        self.db = db

    def run_ocr(self, letter_id: int, user_id: int) -> Letter:
        letter = self.db.get(Letter, letter_id)
        if not letter or letter.user_id != user_id:
            raise DomainError("Brief nicht gefunden")

        if not letter.files:
            raise DomainError("Keine Dateien zum Verarbeiten")

        letter.ocr_status = "processing"
        self.db.commit()

        all_texts = []
        try:
            for file in letter.files:
                file_path = os.path.join(settings.FILES_DIR, str(user_id), file.filename)
                if not os.path.exists(file_path):
                    continue

                text = self._extract_text(file_path, file.content_type)
                file.ocr_text = text
                all_texts.append(text)

            letter.ocr_text = "\n\n---\n\n".join(all_texts) if all_texts else None
            letter.ocr_status = "done"
            self.db.commit()
        except Exception as e:
            letter.ocr_status = "error"
            self.db.commit()
            raise DomainError(f"OCR-Fehler: {str(e)}")

        self.db.refresh(letter)

        # Welle 2B: mail.ocr_ready an life-ops-Event-Spine, best-effort.
        if letter.ocr_text:
            try:
                event_publisher.publish_ocr_ready(
                    letter_id=letter.id,
                    title=letter.title,
                    text_length=len(letter.ocr_text),
                    page_count=len(all_texts),
                )
            except Exception as e:
                logger.warning("mail.ocr_ready publish failed: %s", e)

        return letter

    def _extract_text(self, file_path: str, content_type: str) -> str:
        if content_type == "application/pdf":
            return self._ocr_pdf(file_path)
        else:
            return self._ocr_image(file_path)

    def _ocr_image(self, file_path: str) -> str:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="deu")
        return text.strip()

    def _ocr_pdf(self, file_path: str) -> str:
        """Convert PDF pages to images via pdftoppm, then OCR each page."""
        texts = []
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["pdftoppm", "-png", "-r", "300", file_path, os.path.join(tmpdir, "page")],
                check=True,
                timeout=120,
            )
            # pdftoppm creates page-1.png, page-2.png, etc.
            pages = sorted(
                f for f in os.listdir(tmpdir) if f.endswith(".png")
            )
            for page_file in pages:
                page_path = os.path.join(tmpdir, page_file)
                image = Image.open(page_path)
                text = pytesseract.image_to_string(image, lang="deu")
                texts.append(text.strip())
        return "\n\n".join(texts)
