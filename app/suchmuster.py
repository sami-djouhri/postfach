"""LIKE-Muster aus einer Nutzereingabe.

`%` und `_` sind in LIKE Platzhalter. Ohne Maskierung findet die Suche nach
"_" jeden Brief, und "100%" passt auf alles, was mit "100" beginnt. Keine
Injection (der Wert ist gebunden), nur eine falsche Trefferliste.
Jede Stelle, die das Muster nutzt, braucht dazu `escape=ESCAPE`.
"""

ESCAPE = "\\"


def enthaelt(text: str) -> str:
    """Muster fuer "kommt irgendwo vor", mit maskierten Platzhaltern."""
    sauber = text.replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")
    return f"%{sauber}%"
