import os
from io import BytesIO

from fpdf import FPDF
from PIL import Image

from app.config import settings
from app.models import Letter


class PdfService:
    def generate(self, letter: Letter, user_id: int) -> bytes:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Cover page with metadata
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 15, letter.title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 12)
        meta_lines = []
        if letter.sender:
            meta_lines.append(f"Absender: {letter.sender}")
        if letter.category:
            meta_lines.append(f"Kategorie: {letter.category}")
        if letter.received_date:
            meta_lines.append(f"Empfangsdatum: {letter.received_date}")
        if letter.letter_date:
            meta_lines.append(f"Briefdatum: {letter.letter_date}")
        if letter.tags:
            tag_names = ", ".join(t.name for t in letter.tags)
            meta_lines.append(f"Tags: {tag_names}")

        for line in meta_lines:
            pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")

        if letter.llm_summary:
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Zusammenfassung:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, letter.llm_summary)

        if letter.notes:
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Notizen:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 6, letter.notes)

        # Embed scan images
        for file in letter.files:
            if file.content_type.startswith("image/"):
                file_path = os.path.join(settings.FILES_DIR, str(user_id), file.filename)
                if os.path.exists(file_path):
                    pdf.add_page()
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.cell(
                        0, 6,
                        f"Scan: {file.original_filename} (Seite {file.page_number})",
                        new_x="LMARGIN", new_y="NEXT",
                    )
                    pdf.ln(2)
                    try:
                        img = Image.open(file_path)
                        img_w, img_h = img.size
                        # Scale to fit page width (max ~180mm)
                        max_w = 180
                        max_h = 250
                        ratio = min(max_w / (img_w * 0.264583), max_h / (img_h * 0.264583))
                        w_mm = img_w * 0.264583 * ratio
                        h_mm = img_h * 0.264583 * ratio
                        pdf.image(file_path, x=15, w=w_mm, h=h_mm)
                    except Exception:
                        pdf.cell(0, 8, "(Bild konnte nicht eingebettet werden)")

        # OCR text page
        if letter.ocr_text:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, "OCR-Text", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
            pdf.set_font("Courier", "", 9)
            pdf.multi_cell(0, 4, letter.ocr_text)

        return bytes(pdf.output())
