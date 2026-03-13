"""
Dienstanweisungen-Datenbank (SQLite)
Speichert Metadaten zu erstellten Dienstanweisungen – keine Word-Inhalte,
nur Verweise auf die Dateien und durchsuchbare Felder.
"""
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from config import BASE_DIR

DB_ORDNER = os.path.join(BASE_DIR, "database SQL")
DB_PFAD   = os.path.join(DB_ORDNER, "dienstanweisungen.db")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS dienstanweisungen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    erstellt_am     TEXT    NOT NULL,          -- ISO-Datum der DB-Eintragung
    titel           TEXT    NOT NULL,
    inhalt          TEXT    DEFAULT '',        -- Freitext (Kopie des Inhalts)
    ausrichtung     TEXT    DEFAULT 'hoch',    -- hoch | quer
    schriftgroesse  INTEGER DEFAULT 11,
    pfad            TEXT    NOT NULL           -- vollständiger Dateipfad
);
"""

# ──────────────────────────────────────────────────────────────────────────────
#  Internes Datenbankmanagement
# ──────────────────────────────────────────────────────────────────────────────

def _ensured_db() -> str:
    """Stellt sicher, dass der DB-Ordner existiert und das Schema angelegt ist."""
    os.makedirs(DB_ORDNER, exist_ok=True)
    con = sqlite3.connect(DB_PFAD, timeout=5)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous  = NORMAL")
    con.execute("PRAGMA busy_timeout  = 5000")
    con.execute(_CREATE_SQL)
    con.commit()
    con.close()
    return DB_PFAD


@contextmanager
def _db():
    """Context-Manager: liefert eine Row-Factory-Connection."""
    _ensured_db()
    con = sqlite3.connect(DB_PFAD, timeout=5)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous  = NORMAL")
    con.execute("PRAGMA busy_timeout  = 5000")
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ──────────────────────────────────────────────────────────────────────────────
#  Schreiben
# ──────────────────────────────────────────────────────────────────────────────

def eintrag_speichern(
    titel: str,
    inhalt: str,
    ausrichtung: str,
    schriftgroesse: int,
    pfad: str,
) -> int:
    """Legt einen neuen Datensatz an. Gibt die neue Row-ID zurück."""
    with _db() as con:
        cur = con.execute(
            """
            INSERT INTO dienstanweisungen
              (erstellt_am, titel, inhalt, ausrichtung, schriftgroesse, pfad)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                titel,
                inhalt,
                ausrichtung,
                schriftgroesse,
                pfad,
            ),
        )
        return cur.lastrowid


# ──────────────────────────────────────────────────────────────────────────────
#  Lesen
# ──────────────────────────────────────────────────────────────────────────────

def lade_alle() -> list[dict]:
    """Gibt alle Einträge absteigend nach Erstellungsdatum zurück."""
    try:
        with _db() as con:
            rows = con.execute(
                "SELECT * FROM dienstanweisungen ORDER BY erstellt_am DESC"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def eintrag_loeschen(eintrag_id: int) -> None:
    """Löscht einen Datensatz anhand der ID."""
    with _db() as con:
        con.execute("DELETE FROM dienstanweisungen WHERE id = ?", (eintrag_id,))
