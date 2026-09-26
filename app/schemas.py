from datetime import datetime
from pydantic import BaseModel, Field


# --- Auth ---

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    created_at: datetime


# --- Tags ---

class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


class TagOut(BaseModel):
    id: int
    name: str
    color: str


# --- Letter Files ---

class LetterFileOut(BaseModel):
    id: int
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    page_number: int
    ocr_text: str | None
    created_at: datetime


# --- Letters ---

class LetterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    sender: str | None = None
    category: str | None = None
    received_date: str | None = None
    letter_date: str | None = None
    notes: str | None = None
    tag_ids: list[int] = Field(default_factory=list)


class LetterUpdate(BaseModel):
    title: str | None = None
    sender: str | None = None
    category: str | None = None
    received_date: str | None = None
    letter_date: str | None = None
    notes: str | None = None
    is_archived: bool | None = None
    llm_summary: str | None = None
    tag_ids: list[int] | None = None
    # Saganta Phase 2: optional, snoozed_until=None ist nur dann als unsnooze
    # zu werten, wenn das Feld im Payload explizit gesetzt ist, sonst nicht
    # vom Modell zu unterscheiden. routes_letters.update_letter behandelt
    # das gesondert via model_dump(exclude_unset=True).
    snoozed_until: datetime | None = None
    paperless_id: str | None = None


class LetterOut(BaseModel):
    id: int
    title: str
    sender: str | None
    category: str | None
    received_date: str | None
    letter_date: str | None
    ocr_text: str | None
    ocr_status: str
    analysis_status: str = "none"
    llm_summary: str | None
    notes: str | None
    is_archived: bool
    snoozed_until: datetime | None = None
    paperless_id: str | None = None
    created_at: datetime
    updated_at: datetime
    files: list[LetterFileOut]
    tags: list[TagOut]


class LetterListOut(BaseModel):
    id: int
    title: str
    sender: str | None
    category: str | None
    received_date: str | None
    ocr_status: str
    analysis_status: str = "none"
    is_archived: bool
    snoozed_until: datetime | None = None
    paperless_id: str | None = None
    created_at: datetime
    file_count: int
    tags: list[TagOut]


# --- LLM Analysis ---

class FristItem(BaseModel):
    typ: str  # zahlung|kuendigung|antwort|termin
    datum: str  # YYYY-MM-DD
    beschreibung: str


class LlmAnalysisResult(BaseModel):
    absender: str | None = None
    kategorie: str | None = None
    titel: str | None = None
    zusammenfassung: str | None = None
    fristen: list[FristItem] = Field(default_factory=list)
    calendar_synced: int = 0
    calendar_skipped: int = 0
    calendar_errors: list[str] = Field(default_factory=list)
    error: str | None = None


# --- Stats ---

class StatsOut(BaseModel):
    total_letters: int
    archived_letters: int
    pending_ocr: int
    categories: dict[str, int]
    recent_letters: list[LetterListOut]
