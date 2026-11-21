"""LIKE-Platzhalter aus der Eingabe wirken nicht mehr (`app/suchmuster.py`).

Lauf: ``bash run-tests.sh``
"""
import unittest

from sqlalchemy import Column, Integer, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base

from app.suchmuster import ESCAPE, enthaelt

Basis = declarative_base()


class Zeile(Basis):
    __tablename__ = "zeile"
    id = Column(Integer, primary_key=True)
    text = Column(String)


class Suchmuster(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Basis.metadata.create_all(self.engine)
        with Session(self.engine) as s:
            s.add_all([Zeile(text=t) for t in ("Rabatt 100% bis Freitag", "1000 Euro", "a_b", "axb", "c:\\pfad")])
            s.commit()

    def _treffer(self, eingabe):
        with Session(self.engine) as s:
            return sorted(s.scalars(select(Zeile.text).where(Zeile.text.ilike(enthaelt(eingabe), escape=ESCAPE))))

    def test_prozent_und_unterstrich_sind_zeichen(self):
        self.assertEqual(self._treffer("100%"), ["Rabatt 100% bis Freitag"])
        self.assertEqual(self._treffer("_"), ["a_b"])
        self.assertEqual(self._treffer("a_b"), ["a_b"])

    def test_rueckstrich_und_normale_suche(self):
        self.assertEqual(self._treffer("\\"), ["c:\\pfad"])
        self.assertEqual(self._treffer("euro"), ["1000 Euro"])


if __name__ == "__main__":
    unittest.main()
