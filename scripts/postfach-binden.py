#!/usr/bin/env python3
"""Ein bestehendes Postfach an ein Saganta-Konto binden.

WOFUER
Der Briefkasten hat seine eigene Nutzertabelle, aelter als die Saganta-Anmeldung.
``user.sub`` (Migration 0010) ist die Bruecke zwischen beiden. Dieses Skript
setzt sie, fuer genau eine Zeile, sichtbar und wiederholbar.

WARUM NICHT IN DER MIGRATION
Die Migration kann es, braucht dafuer aber ``DEFAULT_OWNER_SUB`` in der Umgebung.
Damit stuende die Kennung eines konkreten Menschen entweder in einer
Geheimnis-Datei oder im Repo. Fuer einen Dienst, der veroeffentlicht werden soll,
ist beides falsch: ein Selbsthoster hat eine andere Kennung, und der Vorbelegung
im Quelltext sieht man nicht an, dass sie nur fuer genau eine Installation
stimmt.

BENUTZUNG
    docker exec -i briefkasten python scripts/postfach-binden.py --zeigen
    docker exec -i briefkasten python scripts/postfach-binden.py \
        --benutzer Polylemmata --sub 1RqW...

Ohne ``--sub`` passiert nichts ausser Anzeigen. Eine bestehende Bindung wird nie
still ueberschrieben: das waere der eine Fehler, der fremde Post freigibt, ohne
dass etwas rot wird.
"""

import argparse
import os
import sqlite3
import sys
from urllib.parse import urlparse


def db_pfad() -> str:
    roh = os.environ.get("DATABASE_URL", "sqlite:////app/data/app.db")
    if not roh.startswith("sqlite"):
        sys.exit(f"Nur SQLite unterstuetzt, DATABASE_URL ist: {roh}")
    # sqlite:////app/data/app.db  ->  /app/data/app.db
    pfad = urlparse(roh).path
    while pfad.startswith("//"):
        pfad = pfad[1:]
    return pfad


def zeigen(conn) -> None:
    print(f"{'id':>3}  {'benutzer':<24} {'anzeigename':<20} sub")
    for zeile in conn.execute(
        "SELECT id, username, display_name, sub FROM user ORDER BY id"
    ):
        sub = zeile[3] or "(nicht gebunden)"
        print(f"{zeile[0]:>3}  {zeile[1]:<24} {zeile[2]:<20} {sub}")


def binden(conn, benutzer: str, sub: str) -> int:
    vorhanden = conn.execute(
        "SELECT username FROM user WHERE sub = ?", (sub,)
    ).fetchone()
    if vorhanden:
        if vorhanden[0] == benutzer:
            print(f"Schon gebunden: '{benutzer}' haengt an diesem Konto. Nichts zu tun.")
            return 0
        sys.exit(
            f"Abbruch: Der Sub haengt bereits an '{vorhanden[0]}'. "
            "Erst dort loesen, wenn das wirklich umziehen soll."
        )

    zeile = conn.execute(
        "SELECT id, sub FROM user WHERE username = ?", (benutzer,)
    ).fetchone()
    if not zeile:
        sys.exit(f"Abbruch: Kein Nutzer '{benutzer}'. Mit --zeigen nachsehen.")
    if zeile[1]:
        sys.exit(
            f"Abbruch: '{benutzer}' haengt schon an Konto {zeile[1]}. "
            "Eine bestehende Bindung wird nicht still ueberschrieben."
        )

    conn.execute("UPDATE user SET sub = ? WHERE id = ?", (sub, zeile[0]))
    conn.commit()
    anzahl = conn.execute(
        "SELECT count(*) FROM letter WHERE user_id = ?", (zeile[0],)
    ).fetchone()[0]
    print(f"Gebunden: '{benutzer}' an {sub}. {anzahl} Brief(e) sind darueber erreichbar.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zeigen", action="store_true", help="Nur den Stand anzeigen")
    p.add_argument("--benutzer", help="Benutzername im Briefkasten")
    p.add_argument("--sub", help="Saganta-Konto (better-auth user.id)")
    a = p.parse_args()

    conn = sqlite3.connect(db_pfad())
    try:
        if a.zeigen or not (a.benutzer and a.sub):
            zeigen(conn)
            if not a.zeigen:
                print("\n--benutzer und --sub angeben, um zu binden.")
            return 0
        return binden(conn, a.benutzer, a.sub)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
