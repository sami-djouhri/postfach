"""Gemeinsame Hilfe: eine Wegwerf-SQLite mit dem ECHTEN Schema aus den Migrationen.

Bewusst ``alembic upgrade`` und nicht ``Base.metadata.create_all``: nur so gibt
es den FTS5-Index samt Triggern, und nur so prueft ein Test das Schema, das der
Dienst beim Start wirklich bekommt (``CMD alembic upgrade head`` im Dockerfile).
"""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def _alembic_config():
    from alembic.config import Config

    # Der Testlauf startet mit -w /app (run-tests.sh), dort liegt alembic.ini.
    ini = Path.cwd() / "alembic.ini"
    if not ini.is_file():
        raise RuntimeError(f"alembic.ini nicht gefunden unter {ini}, Lauf ueber run-tests.sh")
    # Ohne Dateinamen: ``env.py`` ruft sonst ``fileConfig`` auf, und das
    # schaltet alle schon angelegten Logger ab (disable_existing_loggers).
    # test_mandant prueft per assertLogs auf ``app.tenant_auth`` und bekaeme
    # danach nichts mehr zu sehen, je nach Reihenfolge der Testdateien.
    cfg = Config()
    cfg.set_main_option("script_location", str(Path.cwd() / "migrations"))
    return cfg


@contextmanager
def _datenbank_url(url: str):
    alt = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        yield
    finally:
        if alt is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = alt


def neue_datei() -> str:
    ordner = tempfile.mkdtemp(prefix="postfach-pruefung-")
    return os.path.join(ordner, "pruefung.db")


def migriere(pfad: str, ziel: str = "head") -> None:
    from alembic import command
    with _datenbank_url(f"sqlite:///{pfad}"):
        command.upgrade(_alembic_config(), ziel)


def zurueck(pfad: str, ziel: str = "-1") -> None:
    from alembic import command
    with _datenbank_url(f"sqlite:///{pfad}"):
        command.downgrade(_alembic_config(), ziel)


def engine_fuer(pfad: str):
    from sqlalchemy import create_engine, event

    engine = create_engine(f"sqlite:///{pfad}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine
