"""Der Abdeckungs-Riegel des Loeschwegs.

Er braucht keine Daten und keine laufende Datenbank: das Soll kommt aus den
SQLAlchemy-Metadaten, also aus den Modellen dieses Dienstes. Wird er rot, ist
eine Tabelle hinzugekommen, die den Mandanten traegt, aber in keinem Schritt von
``app/konto.py`` steht -- oder ein Kind hat sein ``ondelete="CASCADE"`` verloren.

Die Antwort darauf ist nie "Test anpassen". Entweder bekommt die Tabelle einen
Schritt, oder sie wird ausdruecklich als gemeinsamer Bestand erklaert. Ohne
diesen Riegel faellt eine neue Tabelle still aus dem Loeschweg, und ein Lauf
meldet weiterhin Erfolg.
"""

from app import konto_mechanik as mechanik
from app import models  # noqa: F401  (fuellt Base.metadata)
from app.db import Base
from app.konto import PLAN


def test_der_loeschplan_deckt_alle_tabellen_ab():
    assert mechanik.abdeckung_pruefen(PLAN, Base.metadata) == []


# Schritte, die bewusst auf eine Tabelle **ausserhalb der Modelle** zeigen.
# `letter_vec` ist eine vec0-Virtualtabelle, die `services/semantic_service.py`
# per rohem SQL anlegt; sie kann in keinem SQLAlchemy-Modell stehen und keinen
# Fremdschluessel haben. Die Liste ist hier und nicht im Plan, damit sie beim
# Lesen des Tests auffaellt: jeder Eintrag ist eine Tabelle, bei der die
# Modell-Pruefung strukturell nicht greift.
#
# Dass es sie wirklich gibt, wird an zwei anderen Stellen bemerkt: ein
# Tippfehler laesst den Loeschlauf mit "no such table" scheitern (die
# Transaktion bricht, nichts ist halb geloescht), und `ungedeckte_live_tabellen`
# meldet die echte Tabelle dann als in keinem Schritt genannt.
AUSSERHALB_DER_MODELLE = {"letter_vec"}


def test_jeder_schritt_nennt_eine_bekannte_tabelle():
    """Ein Tippfehler im Tabellennamen trifft nie und meldet trotzdem 0 Zeilen."""
    bekannt = set(Base.metadata.tables) | set(PLAN.per_trigger) | AUSSERHALB_DER_MODELLE
    for schritt in PLAN.schritte:
        assert schritt.tabelle in bekannt, (
            f"Schritt nennt '{schritt.tabelle}', das es weder in den Modellen noch "
            f"in AUSSERHALB_DER_MODELLE gibt"
        )


def test_die_einbettungen_stehen_im_plan():
    """Der Fund vom 2026-10-06, als Test festgehalten.

    `letter_vec` haelt 384-dimensionale Einbettungen der Briefinhalte. Sie ist
    eine Virtualtabelle, kann also keinen Fremdschluessel haben und faellt
    nicht per CASCADE mit dem Nutzer. Ein Loeschweg ohne diesen Schritt meldete
    "sauber" und liess die Einbettung des geloeschten Briefs stehen, gemessen
    an einer Kopie der Live-Datenbank.
    """
    tabellen = {s.tabelle for s in PLAN.schritte}
    assert "letter_vec" in tabellen, (
        "Ohne diesen Schritt bleiben die Einbettungen der Briefinhalte stehen"
    )
    # Und vor `user`: danach gibt es die Briefe nicht mehr, auf die die
    # Unterabfrage zeigt.
    reihenfolge = [s.tabelle for s in PLAN.schritte]
    assert reihenfolge.index("letter_vec") < reihenfolge.index("user"), (
        "letter_vec muss vor user fallen, sonst findet die Unterabfrage keine Briefe"
    )


def test_leere_metadaten_brechen_laut():
    """Blinde Pruefung ist schlimmer als keine, denn sie meldet "sauber"."""
    import pytest
    from sqlalchemy import MetaData

    with pytest.raises(RuntimeError):
        mechanik.abdeckung_pruefen(PLAN, MetaData())
