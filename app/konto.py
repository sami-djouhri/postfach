"""Der Loeschweg dieses Dienstes: welche Tabelle in welcher Reihenfolge faellt.

Die Mechanik liegt in ``konto_mechanik.py`` (dort auch, warum es hier keine
Netzroute gibt und wie die vier Kopien abgeglichen werden). Hier steht nur, was
dieser Dienst ueber seine eigenen Tabellen weiss.

    docker exec -w /app briefkasten python -m app.konto --sub X [--loeschen]

EIN SCHRITT, UND DAS IST KEIN VERSEHEN
=========================================

Von acht Tabellen traegt genau **eine** den Mandanten: ``user.sub``. Alle
uebrigen haengen per ``ondelete="CASCADE"`` daran, teils ueber zwei Glieder
(``letter_file`` -> ``letter`` -> ``user``). Der Plan braucht deshalb nur den
einen Schritt, und die Abdeckungspruefung loest die Ketten auf und wuerde sich
melden, wenn eine davon ihr CASCADE verloere.

⚠️ **Das traegt allein wegen ``PRAGMA foreign_keys=ON``** (``db.py``, live
gegengeprueft). Ohne das Pragma setzt SQLite Fremdschluessel gar nicht durch:
der Nutzer waere weg und jeder Brief, jeder Korrespondent und jede Sitzung
blieben als Waise stehen, ohne eine einzige Fehlermeldung. Das ist in diesem
Dienst die empfindlichste Stelle des ganzen Loeschwegs, weil hier **alles** an
einer Kante haengt.

DER ORDNERNAME IST DIE ID, NICHT DER SUB
===========================================

Briefdateien liegen unter ``FILES_DIR/<user.id>/``, also unter der
**numerischen** Kennung, nicht unter dem ``sub`` (siehe
``services/letter_service.py:153``). Wer den ``sub`` als Ordnernamen annimmt,
loescht nichts und meldet trotzdem Erfolg: die Briefe bleiben als PDF auf der
Platte liegen, waehrend die Datenbank sauber aussieht. Die Zuordnung wird
deshalb vor dem Loeschen aus der Datenbank gelesen.

Zu den lokalen Konten ohne ``sub``: ``user.sub IS NULL`` heisst hier nicht
"gehoert allen", sondern "lokales Konto ohne Saganta-Bindung", also eine zweite
Anmeldetuer. Sie werden von diesem Loeschweg bewusst **nicht** getroffen, denn
sie gehoeren keinem Saganta-Mandanten; ``verwaiste-mandanten.py`` meldet sie
gesondert.
"""

from __future__ import annotations

import os
from pathlib import Path

from app import konto_mechanik as mechanik

#: Die Briefe dieses Mandanten, als Unterabfrage. An ihnen haengt alles, was
#: nicht per Fremdschluessel mitfaellt.
_MEINE_BRIEFE = "SELECT id FROM letter WHERE user_id IN (SELECT id FROM user WHERE sub = :sub)"

PLAN = mechanik.Plan(
    dienst="briefkasten",
    schritte=(
        # ZUERST die Einbettungen, und das war der Fund dieser Runde.
        #
        # `letter_vec` ist eine `vec0`-Virtualtabelle und kann **keinen**
        # Fremdschluessel haben. Ein Loeschweg, der nur `user` nimmt, meldet
        # deshalb "sauber" und laesst die Einbettung des geloeschten Briefs
        # stehen: gemessen am 2026-10-06 blieb in einer Kopie der Live-Datenbank
        # genau das zurueck (rowid 2 in `letter_vec`, waehrend `letter` nur noch
        # die 1 kannte). Ein 384-dimensionaler Vektor kodiert den Briefinhalt
        # und erlaubt Aehnlichkeitssuche; er ist Nutzerinhalt, nicht Verwaltung.
        #
        # ⚠️ Vor `user`, denn die Unterabfrage braucht die Briefe noch.
        # `letter_vec_meta` und `paperless_import_map` tragen dagegen
        # `ON DELETE CASCADE` auf `letter` und brauchen keinen eigenen Schritt;
        # geprueft wird das von `abdeckung_pruefen`.
        mechanik.Schritt(
            tabelle="letter_vec",
            wo=f"rowid IN ({_MEINE_BRIEFE})",
            warum="Einbettungen der Briefinhalte (vec0, kein Fremdschluessel moeglich)",
        ),
        mechanik.eigene(
            "user", spalte="sub",
            warum="der Nutzer, und per CASCADE Briefe, Dateien, Tags, Korrespondenten, "
                  "Vertragskonten, Sitzungen, Einbettungs-Vermerke und Paperless-Zuordnung",
        ),
    ),
    # Der Volltextindex haelt Titel, Absender, OCR-Text, LLM-Zusammenfassung
    # und Notizen im **Klartext**. Er faellt nicht ueber einen Fremdschluessel,
    # sondern ueber die FTS-Trigger auf `letter`, die beim CASCADE-Loeschen
    # feuern. Hier erklaert, damit die Pruefungen ihn als bedacht verbuchen
    # statt ihn gar nicht zu sehen.
    per_trigger=frozenset({"letter_fts"}),
)


def dateien(db, sub: str) -> list[Path]:
    """Die Briefdateien dieses Mandanten.

    Gelesen wird die numerische ``user.id``, denn danach heisst der Ordner.
    Laeuft vor den Loeschschritten: danach gibt es die Zeile nicht mehr, die die
    Zuordnung traegt.
    """
    from app.config import settings
    from sqlalchemy import text

    kennungen = db.execute(
        text("SELECT id FROM user WHERE sub = :sub"), {"sub": sub}
    ).scalars().all()

    wurzel = Path(settings.FILES_DIR).resolve()
    pfade: list[Path] = []
    for kennung in kennungen:
        ordner = (wurzel / str(kennung)).resolve()
        # Schranke: geprueft wird der aufgeloeste Pfad, nicht der Text. Die
        # Kennung ist hier eine Zahl aus der eigenen Datenbank, die Pruefung
        # kostet eine Zeile und haelt auch dann, wenn das einmal nicht mehr
        # stimmt.
        if ordner != wurzel and ordner.is_relative_to(wurzel):
            pfade.append(ordner)
    return pfade


if __name__ == "__main__":
    from app import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from app.db import Base, SessionLocal

    raise SystemExit(
        mechanik.als_programm(PLAN, Base.metadata, SessionLocal, dateien=dateien))
