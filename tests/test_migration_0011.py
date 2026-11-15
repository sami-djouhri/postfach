"""Migration 0011 (frist_bis, erledigt_am) gegen das bisherige Schema.

Der Dienst fuehrt beim Start ``alembic upgrade head`` aus (Dockerfile, CMD).
Geprueft wird deshalb genau dieser Weg auf einer Wegwerf-Datei: erst der Stand
0010 mit einem erfundenen Brief, dann ``head``, dann ``downgrade -1`` zurueck.
Der Brief muss alle drei Schritte ueberleben, sonst wuerde ein Start den
Bestand beschaedigen.

Lauf: ``bash run-tests.sh``
"""
import unittest

from sqlalchemy import text

from _wegwerf_db import engine_fuer, migriere, neue_datei, zurueck


def spalten(engine, tabelle="letter"):
    with engine.connect() as c:
        return {r[1] for r in c.exec_driver_sql(f"PRAGMA table_info({tabelle})")}


class Migration0011(unittest.TestCase):
    def setUp(self):
        self.pfad = neue_datei()
        migriere(self.pfad, "0010")
        self.engine = engine_fuer(self.pfad)
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            c.execute(text(
                "INSERT INTO user (id, username, password_hash, display_name) "
                "VALUES (1, 'pruefkonto', 'x', 'Pruefkonto')"
            ))
            c.execute(text(
                "INSERT INTO letter (id, user_id, title, sender, ocr_text, ocr_status, "
                "analysis_status, is_archived) VALUES (7, 1, 'Erfundener Brief', "
                "'Muster GmbH', 'zahlbar bis 15.12.2026', 'done', 'none', 0)"
            ))

    def test_vorher_fehlen_die_spalten(self):
        """Gegenprobe: sonst bewiese der naechste Test nichts."""
        self.assertNotIn("frist_bis", spalten(self.engine))
        self.assertNotIn("erledigt_am", spalten(self.engine))

    def test_upgrade_head_legt_an_und_laesst_den_bestand(self):
        migriere(self.pfad, "head")
        s = spalten(self.engine)
        self.assertIn("frist_bis", s)
        self.assertIn("erledigt_am", s)
        with self.engine.connect() as c:
            zeile = c.execute(text(
                "SELECT title, frist_bis, erledigt_am FROM letter WHERE id = 7"
            )).one()
            self.assertEqual(zeile[0], "Erfundener Brief")
            self.assertIsNone(zeile[1])
            self.assertIsNone(zeile[2])
            # Der Volltext-Index haengt per Trigger an letter und muss weiter tragen.
            treffer = c.execute(text(
                "SELECT rowid FROM letter_fts WHERE letter_fts MATCH 'zahlbar'"
            )).all()
            self.assertEqual([r[0] for r in treffer], [7])
            version = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
            self.assertEqual(version, "0011")

    def test_schreiben_nach_upgrade_haelt_den_index_aktuell(self):
        migriere(self.pfad, "head")
        with self.engine.begin() as c:
            c.execute(text("UPDATE letter SET frist_bis = '2026-12-15' WHERE id = 7"))
        with self.engine.connect() as c:
            self.assertEqual(
                c.execute(text("SELECT frist_bis FROM letter WHERE id = 7")).scalar(),
                "2026-12-15",
            )
            treffer = c.execute(text(
                "SELECT rowid FROM letter_fts WHERE letter_fts MATCH 'zahlbar'"
            )).all()
            self.assertEqual([r[0] for r in treffer], [7])

    def test_downgrade_geht_zurueck_und_wieder_vor(self):
        migriere(self.pfad, "head")
        with self.engine.begin() as c:
            c.execute(text("UPDATE letter SET frist_bis = '2026-12-15' WHERE id = 7"))
        zurueck(self.pfad, "-1")
        s = spalten(self.engine)
        self.assertNotIn("frist_bis", s)
        self.assertNotIn("erledigt_am", s)
        with self.engine.connect() as c:
            self.assertEqual(
                c.execute(text("SELECT version_num FROM alembic_version")).scalar(), "0010")
            self.assertEqual(
                c.execute(text("SELECT title FROM letter WHERE id = 7")).scalar(),
                "Erfundener Brief")
            indizes = {r[1] for r in c.exec_driver_sql("PRAGMA index_list(letter)")}
            self.assertNotIn("ix_letter_frist_offen", indizes)
        # Und wieder vor: der Weg muss wiederholbar sein.
        migriere(self.pfad, "head")
        self.assertIn("frist_bis", spalten(self.engine))


if __name__ == "__main__":
    unittest.main()
