"""
Beschwerden-Datenbank
Eigene SQLite-Datenbank (beschwerden.db) – folgt dem Muster verspaetung_db.py

Backup : automatisch via Backup-Manager (glob *.db im DB-Ordner)
Turso  : über push_row() nach jedem Write (TABLE_MAP in turso_sync.py)
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from config import BASE_DIR as _BASE_DIR

_DB_PFAD = Path(_BASE_DIR) / "database SQL" / "beschwerden.db"

# ── Konstanten ────────────────────────────────────────────────────────────────

KATEGORIEN = [
    "Verhalten Mitarbeiter",
    "Wartezeit / Reaktionszeit",
    "Kommunikation",
    "Ausstattung / Material",
    "Hygiene",
    "Dokumentation",
    "Behandlung / Versorgung",
    "Sonstiges",
]

PRIORITAETEN = ["Niedrig", "Mittel", "Hoch", "Kritisch"]

STATUS_OPTIONEN = ["Offen", "In Bearbeitung", "Erledigt", "Abgewiesen"]

QUELLEN = ["Freitext", "Word-Datei", "PDF-Datei", "E-Mail"]


# ── Verbindung / Init ─────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PFAD), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous  = NORMAL")
    conn.execute("PRAGMA busy_timeout  = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _push(table: str, row_id: int) -> None:
    """Async-Push einer einzelnen Zeile nach Turso."""
    try:
        from database.turso_sync import push_row
        conn = sqlite3.connect(str(_DB_PFAD), timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        conn.close()
        if row:
            push_row(str(_DB_PFAD), table, dict(row))
    except Exception:
        pass


def _init_db() -> None:
    _DB_PFAD.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS beschwerden (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            datum_eingang           TEXT    NOT NULL,
            quelle                  TEXT    NOT NULL DEFAULT 'Freitext',
            quelldatei              TEXT    NOT NULL DEFAULT '',
            originaltext            TEXT    NOT NULL DEFAULT '',
            betroffener             TEXT    NOT NULL DEFAULT '',
            name_beschwerdefuehrer  TEXT    NOT NULL DEFAULT '',
            email_beschwerdefuehrer TEXT    NOT NULL DEFAULT '',
            kategorie               TEXT    NOT NULL DEFAULT 'Sonstiges',
            prioritaet              TEXT    NOT NULL DEFAULT 'Mittel',
            status                  TEXT    NOT NULL DEFAULT 'Offen',
            massnahme               TEXT    NOT NULL DEFAULT '',
            gemini_antwort          TEXT    NOT NULL DEFAULT '',
            erstellt_am             TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            geaendert_am            TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS beschwerde_antworten (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            beschwerde_id   INTEGER NOT NULL,
            datum           TEXT    NOT NULL,
            empfaenger      TEXT    NOT NULL DEFAULT '',
            betreff         TEXT    NOT NULL DEFAULT '',
            antworttext     TEXT    NOT NULL DEFAULT '',
            erstellt_am     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (beschwerde_id) REFERENCES beschwerden(id) ON DELETE CASCADE
        );
        """)
        conn.commit()


# ── Beschwerden CRUD ──────────────────────────────────────────────────────────

def beschwerde_speichern(daten: dict) -> int:
    """Neue Beschwerde anlegen. Gibt die neue ID zurück."""
    _init_db()
    now = datetime.now().strftime("%d.%m.%Y")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO beschwerden
                (datum_eingang, quelle, quelldatei, originaltext, betroffener,
                 name_beschwerdefuehrer, email_beschwerdefuehrer,
                 kategorie, prioritaet, status, massnahme)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                daten.get("datum_eingang", now),
                daten.get("quelle", "Freitext"),
                daten.get("quelldatei", ""),
                daten.get("originaltext", ""),
                daten.get("betroffener", ""),
                daten.get("name_beschwerdefuehrer", ""),
                daten.get("email_beschwerdefuehrer", ""),
                daten.get("kategorie", "Sonstiges"),
                daten.get("prioritaet", "Mittel"),
                daten.get("status", "Offen"),
                daten.get("massnahme", ""),
            ),
        )
        conn.commit()
        rid = cur.lastrowid
    _push("beschwerden", rid)
    return rid


def beschwerde_aktualisieren(bid: int, daten: dict) -> None:
    """Bestehende Beschwerde aktualisieren."""
    _init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE beschwerden SET
                datum_eingang=?, quelle=?, quelldatei=?, originaltext=?,
                betroffener=?, name_beschwerdefuehrer=?, email_beschwerdefuehrer=?,
                kategorie=?, prioritaet=?, status=?, massnahme=?, gemini_antwort=?,
                geaendert_am=datetime('now','localtime')
            WHERE id=?
            """,
            (
                daten.get("datum_eingang", ""),
                daten.get("quelle", "Freitext"),
                daten.get("quelldatei", ""),
                daten.get("originaltext", ""),
                daten.get("betroffener", ""),
                daten.get("name_beschwerdefuehrer", ""),
                daten.get("email_beschwerdefuehrer", ""),
                daten.get("kategorie", "Sonstiges"),
                daten.get("prioritaet", "Mittel"),
                daten.get("status", "Offen"),
                daten.get("massnahme", ""),
                daten.get("gemini_antwort", ""),
                bid,
            ),
        )
        conn.commit()
    _push("beschwerden", bid)


def beschwerde_loeschen(bid: int) -> None:
    """Beschwerde und zugehörige Antworten löschen."""
    _init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM beschwerde_antworten WHERE beschwerde_id=?", (bid,))
        conn.execute("DELETE FROM beschwerden WHERE id=?", (bid,))
        conn.commit()


def lade_beschwerden(
    status: str = "Alle",
    prioritaet: str = "Alle",
    kategorie: str = "Alle",
    suche: str = "",
) -> list[dict]:
    """Alle Beschwerden laden, optional gefiltert. Neueste zuerst."""
    _init_db()
    sql = "SELECT * FROM beschwerden WHERE 1=1"
    params: list = []
    if status and status != "Alle":
        sql += " AND status=?"
        params.append(status)
    if prioritaet and prioritaet != "Alle":
        sql += " AND prioritaet=?"
        params.append(prioritaet)
    if kategorie and kategorie != "Alle":
        sql += " AND kategorie=?"
        params.append(kategorie)
    if suche.strip():
        s = f"%{suche.strip()}%"
        sql += (
            " AND (originaltext LIKE ? OR name_beschwerdefuehrer LIKE ?"
            " OR email_beschwerdefuehrer LIKE ? OR betroffener LIKE ?)"
        )
        params += [s, s, s, s]
    sql += " ORDER BY id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def lade_beschwerde(bid: int) -> dict | None:
    """Einzelne Beschwerde laden."""
    _init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM beschwerden WHERE id=?", (bid,)).fetchone()
    return dict(row) if row else None


# ── Antworten CRUD ────────────────────────────────────────────────────────────

def antwort_speichern(daten: dict) -> int:
    """Neue Antwort speichern. Gibt neue ID zurück."""
    _init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO beschwerde_antworten
                (beschwerde_id, datum, empfaenger, betreff, antworttext)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                daten["beschwerde_id"],
                daten.get("datum", datetime.now().strftime("%d.%m.%Y")),
                daten.get("empfaenger", ""),
                daten.get("betreff", ""),
                daten.get("antworttext", ""),
            ),
        )
        conn.commit()
        rid = cur.lastrowid
    _push("beschwerde_antworten", rid)
    return rid


def lade_antworten(beschwerde_id: int) -> list[dict]:
    """Alle Antworten zu einer Beschwerde laden. Neueste zuerst."""
    _init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM beschwerde_antworten WHERE beschwerde_id=? ORDER BY id DESC",
            (beschwerde_id,),
        ).fetchall()
    return [dict(r) for r in rows]
