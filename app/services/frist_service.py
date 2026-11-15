"""Fristen: Vorschlag aus dem Brieftext, offene Fristen, erledigt.

Entscheid 2026-11-13: eine Frist wird VORGESCHLAGEN, gesetzt wird sie erst,
wenn der Nutzer bestaetigt (``PUT /api/letters/{id}`` mit ``frist_bis``). Nichts
in diesem Modul schreibt ``frist_bis``.

Der Vorschlag ist regelbasiert und laeuft auf dem erkannten Text, nicht auf
einem Sprachmodell: er ist damit bei jedem Aufruf derselbe, kostet nichts und
braucht keine Spalte, um sich zu merken, was ein Modell einmal gesagt hat. Die
Analyse durch das Sprachmodell liefert ihre Fristen weiter in der Antwort von
``/analyze``; die Oberflaeche bietet sie dort ebenfalls zum Uebernehmen an.

Gesucht wird nach zwei Formen:

* ein Datum mit einem Fristwort davor ("zahlbar bis 15.12.2026",
  "spaetestens am 3. Januar 2027"),
* eine Frist relativ zum Brief ("innerhalb von 14 Tagen"), gerechnet ab
  Briefdatum, sonst Eingangsdatum.

Ein Datum ohne Fristwort (Briefkopf, Rechnungsdatum) ist keine Frist. Ein
Zeitraum ("vom 01.10. bis 31.10.2026") auch nicht. Von mehreren Kandidaten gilt
der frueheste, der nicht vor dem Bezugsdatum liegt: die erste Frist ist die, die
man nicht verpassen darf.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Letter

_MONATE = {
    "januar": 1, "jan": 1, "februar": 2, "feb": 2, "maerz": 3, "märz": 3, "mär": 3, "mar": 3,
    "april": 4, "apr": 4, "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10, "okt": 10,
    "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}
_MONATSNAMEN = "|".join(sorted(_MONATE, key=len, reverse=True))

_DATUM_ZAHL = re.compile(r"(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4}|\d{2})(?!\d)")
_DATUM_WORT = re.compile(rf"(?<!\d)(\d{{1,2}})\.\s?({_MONATSNAMEN})\.?\s+(\d{{4}})(?!\d)", re.IGNORECASE)
_DATUM_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")

# Ein Fristwort in den Zeichen vor dem Datum.
_FRISTWORT = re.compile(
    r"\bbis\b|sp(?:ä|ae)testens|f(?:ä|ae)llig|zahlbar|\bfrist|einzureichen|einzahlen"
    r"|zu\s+(?:zahlen|begleichen|überweisen|ueberweisen)|r(?:ü|ue)ckmeldung|antwort\s+bis",
    re.IGNORECASE,
)
# Ein Zeitraum ist keine Frist: "vom 01.10.2026 bis 31.10.2026", "Leistungszeitraum".
_ZEITRAUM = re.compile(r"zeitraum|\bvom\s+\d|\bab\s+\d|g(?:ü|ue)ltig", re.IGNORECASE)

_ZAHLWORT = {
    "einer": 1, "eine": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "zehn": 10, "vierzehn": 14, "einundzwanzig": 21,
    "dreißig": 30, "dreissig": 30,
}
_RELATIV = re.compile(
    r"\b(?:innerhalb|binnen)\s+(?:von\s+)?(\d{1,3}|" + "|".join(_ZAHLWORT) + r")\s+"
    r"(tag|tagen|tage|woche|wochen|monat|monaten|monate)\b",
    re.IGNORECASE,
)

_FENSTER = 60  # Zeichen vor dem Datum, in denen das Fristwort stehen muss
# Das Fenster endet am Satzanfang: ein "Zeitraum" im Satz davor soll die Frist
# im naechsten Satz nicht verdecken. Einfache Zeilenumbrueche zaehlen nicht,
# die Texterkennung bricht mitten im Satz um.
_SATZGRENZE = re.compile(r"[.!?;]\s+(?=[A-ZÄÖÜ])|\n\s*\n")
_HORIZONT_TAGE = 3 * 365  # weiter in der Zukunft ist es eher eine Laufzeit als eine Frist


@dataclass(frozen=True)
class FristVorschlag:
    datum: date
    stelle: str


def _jahr(roh: str) -> int:
    j = int(roh)
    return 2000 + j if j < 100 else j


def _sicheres_datum(j: int, m: int, t: int) -> date | None:
    try:
        return date(j, m, t)
    except ValueError:
        return None


def _plus_monate(d: date, n: int) -> date:
    m = d.month - 1 + n
    j = d.year + m // 12
    m = m % 12 + 1
    return date(j, m, min(d.day, calendar.monthrange(j, m)[1]))


def _stelle(text: str, anfang: int, ende: int) -> str:
    a = max(0, anfang - 40)
    e = min(len(text), ende + 20)
    return " ".join(text[a:e].split())


def _datumskandidaten(text: str):
    for m in _DATUM_ZAHL.finditer(text):
        d = _sicheres_datum(_jahr(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            yield d, m.start(), m.end()
    for m in _DATUM_WORT.finditer(text):
        monat = _MONATE.get(m.group(2).lower())
        d = _sicheres_datum(int(m.group(3)), monat, int(m.group(1))) if monat else None
        if d:
            yield d, m.start(), m.end()
    for m in _DATUM_ISO.finditer(text):
        d = _sicheres_datum(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            yield d, m.start(), m.end()


def frist_aus_text(text: str | None, bezug: date | None = None) -> FristVorschlag | None:
    """Die frueheste Frist im Text, oder None.

    ``bezug`` ist das Datum des Briefes (sonst Eingang). Daten davor sind keine
    Frist, und eine relative Frist ("innerhalb von 14 Tagen") braucht ihn.
    """
    if not text or not text.strip():
        return None
    kandidaten: list[tuple[date, int, int]] = []

    for d, anfang, ende in _datumskandidaten(text):
        vorher = text[max(0, anfang - _FENSTER):anfang]
        grenzen = list(_SATZGRENZE.finditer(vorher))
        if grenzen:
            vorher = vorher[grenzen[-1].end():]
        if not _FRISTWORT.search(vorher):
            continue
        if _ZEITRAUM.search(vorher):
            continue
        kandidaten.append((d, anfang, ende))

    if bezug is not None:
        for m in _RELATIV.finditer(text):
            roh = m.group(1).lower()
            n = int(roh) if roh.isdigit() else _ZAHLWORT[roh]
            einheit = m.group(2).lower()
            if einheit.startswith("tag"):
                d = bezug + timedelta(days=n)
            elif einheit.startswith("woche"):
                d = bezug + timedelta(weeks=n)
            else:
                d = _plus_monate(bezug, n)
            kandidaten.append((d, m.start(), m.end()))

    if bezug is not None:
        kandidaten = [
            k for k in kandidaten
            if bezug <= k[0] <= bezug + timedelta(days=_HORIZONT_TAGE)
        ]
    if not kandidaten:
        return None
    d, anfang, ende = min(kandidaten, key=lambda k: (k[0], k[1]))
    return FristVorschlag(datum=d, stelle=_stelle(text, anfang, ende))


def bezugsdatum(letter: Letter) -> date | None:
    """Briefdatum, sonst Eingang, sonst Anlage des Datensatzes."""
    for roh in (letter.letter_date, letter.received_date):
        if roh:
            try:
                return date.fromisoformat(roh[:10])
            except ValueError:
                continue
    if letter.created_at:
        return letter.created_at.date()
    return None


def vorschlag_fuer(letter: Letter) -> FristVorschlag | None:
    return frist_aus_text(letter.ocr_text, bezugsdatum(letter))


# --- offene Fristen und erledigt ---------------------------------------------

def _offen_basis(user_id: int):
    return select(Letter).where(
        Letter.user_id == user_id,
        Letter.deleted_at.is_(None),
        Letter.erledigt_am.is_(None),
    )


def offene_fristen(db: Session, user_id: int, heute: date) -> list[dict]:
    """Briefe mit bestaetigter, nicht erledigter Frist, die frueheste zuerst."""
    briefe = db.execute(
        _offen_basis(user_id)
        .where(Letter.frist_bis.is_not(None))
        .order_by(Letter.frist_bis.asc(), Letter.id.asc())
    ).scalars().all()
    return [
        {
            "letter": b,
            "tage": (b.frist_bis - heute).days,
            "ueberfaellig": b.frist_bis < heute,
        }
        for b in briefe
    ]


def offene_vorschlaege(db: Session, user_id: int, heute: date,
                       tage_zurueck: int = 60, hoechstens: int = 200) -> list[dict]:
    """Junge, offene Briefe ohne Frist, in deren Text eine Frist steht.

    Nur juengere Briefe: ein Vorschlag soll beim Einsortieren helfen und nicht
    den ganzen Altbestand noch einmal vorlegen. Wer einen Vorschlag nicht will,
    hakt den Brief ab ("Nichts zu tun"), dann erscheint er hier nicht mehr.
    """
    seit = datetime.combine(heute - timedelta(days=tage_zurueck), datetime.min.time())
    briefe = db.execute(
        _offen_basis(user_id)
        .where(
            Letter.frist_bis.is_(None),
            Letter.ocr_text.is_not(None),
            Letter.created_at >= seit,
        )
        .order_by(Letter.created_at.desc())
        .limit(hoechstens)
    ).scalars().all()
    ergebnis = []
    for b in briefe:
        v = vorschlag_fuer(b)
        if v is not None:
            ergebnis.append({"letter": b, "vorschlag": v})
    ergebnis.sort(key=lambda e: e["vorschlag"].datum)
    return ergebnis


def erledigen(letter: Letter, jetzt: datetime | None = None) -> None:
    """Idempotent: ein schon erledigter Brief behaelt seinen ersten Zeitpunkt."""
    if letter.erledigt_am is None:
        letter.erledigt_am = (jetzt or datetime.now(timezone.utc)).replace(tzinfo=None)


def wieder_oeffnen(letter: Letter) -> None:
    letter.erledigt_am = None
