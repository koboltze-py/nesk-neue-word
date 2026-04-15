"""
Mitarbeiter-Sync
Wenn ein neuer Mitarbeiter angelegt wird, werden zusätzlich zu schulungen.db
auch mitarbeiter.db und nesk3.db entsprechend befüllt.
Für jede DB werden nur die relevanten Felder abgefragt/gespeichert.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from config import BASE_DIR as _BASE_DIR

_BASE_SQL = Path(_BASE_DIR) / "database SQL"
_MA_DB    = _BASE_SQL / "mitarbeiter.db"
_NESK_DB  = _BASE_SQL / "nesk3.db"


def _conn(pfad: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(pfad, timeout=5)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous  = NORMAL")
    return conn


def _existiert_in_ma_db(nachname: str, vorname: str) -> bool:
    if not _MA_DB.exists():
        return False
    with _conn(_MA_DB) as c:
        r = c.execute(
            "SELECT id FROM mitarbeiter WHERE nachname=? AND vorname=?",
            (nachname, vorname)
        ).fetchone()
    return r is not None


def _existiert_in_nesk_db(nachname: str, vorname: str) -> bool:
    if not _NESK_DB.exists():
        return False
    with _conn(_NESK_DB) as c:
        r = c.execute(
            "SELECT id FROM mitarbeiter WHERE nachname=? AND vorname=?",
            (nachname, vorname)
        ).fetchone()
    return r is not None


def lade_positionen_ma_db() -> list[str]:
    if not _MA_DB.exists():
        return []
    with _conn(_MA_DB) as c:
        rows = c.execute("SELECT name FROM positionen ORDER BY name").fetchall()
    return [r[0] for r in rows]


def lade_abteilungen_ma_db() -> list[str]:
    if not _MA_DB.exists():
        return []
    with _conn(_MA_DB) as c:
        rows = c.execute("SELECT name FROM abteilungen ORDER BY name").fetchall()
    return [r[0] for r in rows]


def lade_positionen_nesk_db() -> list[str]:
    if not _NESK_DB.exists():
        return []
    with _conn(_NESK_DB) as c:
        rows = c.execute("SELECT name FROM positionen ORDER BY name").fetchall()
    return [r[0] for r in rows]


def lade_abteilungen_nesk_db() -> list[str]:
    if not _NESK_DB.exists():
        return []
    with _conn(_NESK_DB) as c:
        rows = c.execute("SELECT name FROM abteilungen ORDER BY name").fetchall()
    return [r[0] for r in rows]


def sync_in_ma_db(daten: dict) -> bool:
    """
    Legt einen neuen Mitarbeiter in mitarbeiter.db an.
    daten-Keys: nachname, vorname, personalnummer, funktion, position,
                abteilung, email, telefon, eintrittsdatum
    Gibt True zurück wenn neu angelegt, False wenn bereits vorhanden.
    """
    if not _MA_DB.exists():
        return False
    if _existiert_in_ma_db(daten.get("nachname", ""), daten.get("vorname", "")):
        return False
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(_MA_DB) as c:
        c.execute(
            """INSERT INTO mitarbeiter
               (vorname, nachname, personalnummer, funktion, position, abteilung,
                email, telefon, eintrittsdatum, status, erstellt_am, geaendert_am)
               VALUES (?,?,?,?,?,?,?,?,?,'aktiv',?,?)""",
            (daten.get("vorname", ""),
             daten.get("nachname", ""),
             daten.get("personalnummer") or None,
             daten.get("funktion", ""),
             daten.get("position", ""),
             daten.get("abteilung", ""),
             daten.get("email", ""),
             daten.get("telefon", ""),
             daten.get("eintrittsdatum", ""),
             now, now),
        )
        c.commit()
    return True


def sync_in_nesk_db(daten: dict) -> bool:
    """
    Legt einen neuen Mitarbeiter in nesk3.db an.
    Gibt True zurück wenn neu angelegt, False wenn bereits vorhanden.
    """
    if not _NESK_DB.exists():
        return False
    if _existiert_in_nesk_db(daten.get("nachname", ""), daten.get("vorname", "")):
        return False
    now = datetime.now().isoformat(timespec="seconds")
    with _conn(_NESK_DB) as c:
        c.execute(
            """INSERT INTO mitarbeiter
               (vorname, nachname, personalnummer, position, abteilung,
                email, telefon, eintrittsdatum, status, erstellt_am, geaendert_am, funktion)
               VALUES (?,?,?,?,?,?,?,?,'aktiv',?,?,?)""",
            (daten.get("vorname", ""),
             daten.get("nachname", ""),
             daten.get("personalnummer") or None,
             daten.get("position", ""),
             daten.get("abteilung", ""),
             daten.get("email", ""),
             daten.get("telefon", ""),
             daten.get("eintrittsdatum", ""),
             now, now,
             daten.get("funktion", "")),
        )
        c.commit()
    return True


def sync_neuer_mitarbeiter(schulungen_daten: dict, ma_db_daten: dict) -> dict:
    """
    Führt den vollständigen Sync durch.
    schulungen_daten: Basis-Daten für schulungen.db (nachname, vorname, ...)
    ma_db_daten:      Erweiterte Daten für mitarbeiter.db / nesk3.db
    Gibt dict mit {db_name: True/False} zurück.
    """
    merged = {**schulungen_daten, **ma_db_daten}
    return {
        "mitarbeiter.db": sync_in_ma_db(merged),
        "nesk3.db":       sync_in_nesk_db(merged),
    }
