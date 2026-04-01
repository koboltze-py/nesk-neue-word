# -*- coding: utf-8 -*-
"""
Unittests fuer PAX- und Einsatz-Datenbankfunktionen (database/pax_db.py).

Laeuft vollstaendig isoliert mit einer In-Memory-SQLite-Datenbank –
kein Zugriff auf die echte Nesk3-Datenbank.

Ausfuehren:
    python -m pytest test_pax_einsatz_db.py -v
    # oder ohne pytest:
    python test_pax_einsatz_db.py
"""
import sqlite3
import sys
import unittest
from unittest.mock import patch

# --------------------------------------------------------------------------
# Hilfsfunktion: In-Memory-Datenbank mit benoetigtem Schema erstellen
# --------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE tages_pax (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    datum       TEXT NOT NULL UNIQUE,
    pax_zahl    INTEGER NOT NULL DEFAULT 0,
    erfasst_am  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE tages_einsaetze (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    datum           TEXT NOT NULL UNIQUE,
    einsaetze_zahl  INTEGER NOT NULL DEFAULT 0,
    erfasst_am      TEXT DEFAULT (datetime('now','localtime'))
);
"""


def _row_factory(cursor, row):
    """Identische Row-Factory wie in database/connection.py."""
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))


def _make_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = _row_factory
    conn.executescript(_SCHEMA)
    return conn


# --------------------------------------------------------------------------
# Testklasse
# --------------------------------------------------------------------------
class TestPaxFunktionen(unittest.TestCase):
    """Tests fuer speichere_tages_pax, lade_tages_pax, lade_jahres_pax."""

    def setUp(self):
        self.conn = _make_conn()
        # pax_db.get_connection() durch unsere In-Memory-Verbindung ersetzen
        self.patcher = patch("database.pax_db.get_connection", return_value=self.conn)
        self.patcher.start()
        from database import pax_db
        self.pax_db = pax_db

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    # -- speichere / lade Tages-PAX ----------------------------------------

    def test_pax_speichern_und_laden(self):
        self.pax_db.speichere_tages_pax("2026-01-15", 12345)
        result = self.pax_db.lade_tages_pax("2026-01-15")
        self.assertEqual(result, 12345)

    def test_pax_kein_eintrag_gibt_null(self):
        result = self.pax_db.lade_tages_pax("2026-01-01")
        self.assertEqual(result, 0)

    def test_pax_ueberschreiben(self):
        self.pax_db.speichere_tages_pax("2026-02-01", 1000)
        self.pax_db.speichere_tages_pax("2026-02-01", 2500)
        result = self.pax_db.lade_tages_pax("2026-02-01")
        self.assertEqual(result, 2500, "Zweiter Aufruf soll Wert ueberschreiben")

    def test_pax_jahressumme(self):
        self.pax_db.speichere_tages_pax("2026-03-01", 10000)
        self.pax_db.speichere_tages_pax("2026-03-02", 20000)
        self.pax_db.speichere_tages_pax("2026-03-03", 5000)
        result = self.pax_db.lade_jahres_pax(2026)
        self.assertEqual(result, 35000)

    def test_pax_jahressumme_filtert_anderes_jahr(self):
        self.pax_db.speichere_tages_pax("2025-12-31", 99999)
        self.pax_db.speichere_tages_pax("2026-01-01", 100)
        result = self.pax_db.lade_jahres_pax(2026)
        self.assertEqual(result, 100, "Nur Eintraege aus 2026 sollen summiert werden")

    def test_pax_jahressumme_leer_gibt_null(self):
        result = self.pax_db.lade_jahres_pax(2099)
        self.assertEqual(result, 0)

    def test_pax_verschiedene_daten_unabhaengig(self):
        self.pax_db.speichere_tages_pax("2026-03-10", 500)
        self.pax_db.speichere_tages_pax("2026-03-11", 750)
        self.assertEqual(self.pax_db.lade_tages_pax("2026-03-10"), 500)
        self.assertEqual(self.pax_db.lade_tages_pax("2026-03-11"), 750)


class TestEinsatzFunktionen(unittest.TestCase):
    """Tests fuer speichere_tages_einsaetze, lade_tages_einsaetze, lade_jahres_einsaetze."""

    def setUp(self):
        self.conn = _make_conn()
        self.patcher = patch("database.pax_db.get_connection", return_value=self.conn)
        self.patcher.start()
        from database import pax_db
        self.pax_db = pax_db

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    # -- speichere / lade Tages-Einsaetze ----------------------------------

    def test_einsaetze_speichern_und_laden(self):
        self.pax_db.speichere_tages_einsaetze("2026-03-20", 7)
        result = self.pax_db.lade_tages_einsaetze("2026-03-20")
        self.assertEqual(result, 7)

    def test_einsaetze_kein_eintrag_gibt_null(self):
        result = self.pax_db.lade_tages_einsaetze("2026-01-01")
        self.assertEqual(result, 0)

    def test_einsaetze_ueberschreiben(self):
        self.pax_db.speichere_tages_einsaetze("2026-03-21", 3)
        self.pax_db.speichere_tages_einsaetze("2026-03-21", 8)
        result = self.pax_db.lade_tages_einsaetze("2026-03-21")
        self.assertEqual(result, 8, "Zweiter Aufruf soll Wert ueberschreiben")

    def test_einsaetze_jahressumme(self):
        self.pax_db.speichere_tages_einsaetze("2026-01-01", 5)
        self.pax_db.speichere_tages_einsaetze("2026-01-02", 12)
        self.pax_db.speichere_tages_einsaetze("2026-01-03", 3)
        result = self.pax_db.lade_jahres_einsaetze(2026)
        self.assertEqual(result, 20)

    def test_einsaetze_jahressumme_filtert_anderes_jahr(self):
        self.pax_db.speichere_tages_einsaetze("2025-12-31", 999)
        self.pax_db.speichere_tages_einsaetze("2026-01-01", 4)
        result = self.pax_db.lade_jahres_einsaetze(2026)
        self.assertEqual(result, 4)

    def test_einsaetze_jahressumme_leer_gibt_null(self):
        result = self.pax_db.lade_jahres_einsaetze(2099)
        self.assertEqual(result, 0)

    def test_einsaetze_null_speichern(self):
        self.pax_db.speichere_tages_einsaetze("2026-04-01", 0)
        result = self.pax_db.lade_tages_einsaetze("2026-04-01")
        self.assertEqual(result, 0)


class TestPaxUndEinsatzUnabhaengig(unittest.TestCase):
    """Stellt sicher, dass PAX- und Einsatz-Tabellen sich nicht gegenseitig beeinflussen."""

    def setUp(self):
        self.conn = _make_conn()
        self.patcher = patch("database.pax_db.get_connection", return_value=self.conn)
        self.patcher.start()
        from database import pax_db
        self.pax_db = pax_db

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()

    def test_pax_und_einsaetze_getrennt(self):
        self.pax_db.speichere_tages_pax("2026-03-26", 42000)
        self.pax_db.speichere_tages_einsaetze("2026-03-26", 15)
        self.assertEqual(self.pax_db.lade_tages_pax("2026-03-26"), 42000)
        self.assertEqual(self.pax_db.lade_tages_einsaetze("2026-03-26"), 15)

    def test_jahressummen_getrennt(self):
        self.pax_db.speichere_tages_pax("2026-03-26", 10000)
        self.pax_db.speichere_tages_einsaetze("2026-03-26", 5)
        self.assertEqual(self.pax_db.lade_jahres_pax(2026), 10000)
        self.assertEqual(self.pax_db.lade_jahres_einsaetze(2026), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
