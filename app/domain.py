import enum


class DomainError(Exception):
    """Raised for business-rule violations."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class OcrStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class LetterCategory(str, enum.Enum):
    RECHNUNG = "Rechnung"
    VERTRAG = "Vertrag"
    BEHOERDE = "Behoerde"
    VERSICHERUNG = "Versicherung"
    BANK = "Bank"
    GESUNDHEIT = "Gesundheit"
    SONSTIGES = "Sonstiges"


ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
