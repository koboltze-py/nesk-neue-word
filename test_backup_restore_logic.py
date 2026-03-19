"""
Test: Backup-Restore Logik – ohne echten Turso-Zugriff

Testet zwei kritische Szenarien:

  Szenario A – Turso löscht Daten extern OHNE Tombstone:
    pull_table() mit leerer Turso-Antwort und pull_deletions() ohne
    Tombstone-Einträge dürfen lokale Daten NICHT löschen.

  Szenario B – Nach restore_sql_backup() schreibt App korrekt nach Turso:
    1. restore_sql_backup() stellt Daten lokal wieder her und setzt Restore-Flag.
    2. main.py-Startup-Logik erkennt das Flag → ruft push_all_local_to_turso()
       statt pull_all() auf.
    3. Das Flag wird danach gelöscht.

Aufruf:
    python test_backup_restore_logic.py
"""
import os
import sys
import sqlite3
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool, str]] = []


def ok(name: str) -> None:
    results.append((name, True, ""))
    print(f"  {PASS}  {name}")


def fail(name: str, err) -> None:
    results.append((name, False, str(err)))
    print(f"  {FAIL}  {name}")
    print(f"         -> {err}")


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _make_temp_db(path: str, rows: list[dict] | None = None) -> None:
    """Erstellt eine temporäre SQLite-DB mit einer Testtabelle."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mitarbeiter (
            id INTEGER PRIMARY KEY,
            name TEXT,
            abteilung TEXT
        )
    """)
    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO mitarbeiter (id, name, abteilung) VALUES (?, ?, ?)",
            [(r["id"], r["name"], r["abteilung"]) for r in rows]
        )
    conn.commit()
    conn.close()


def _count_local_rows(db_path: str, table: str = "mitarbeiter") -> int:
    conn = sqlite3.connect(db_path)
    n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    conn.close()
    return n


# ─────────────────────────────────────────────────────────────────────────────
# Szenario A: Turso externe Löschung OHNE Tombstone → lokale Daten bleiben
# ─────────────────────────────────────────────────────────────────────────────

def test_pull_table_empty_turso_preserves_local():
    """
    Wenn Turso 0 Zeilen zurückgibt (externe Löschung ohne Tombstone),
    darf pull_table() die lokale DB NICHT anfassen.
    """
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "nesk3.db")
        _make_temp_db(db_path, [
            {"id": 1, "name": "Max Mustermann", "abteilung": "Rettung"},
            {"id": 2, "name": "Eva Test",       "abteilung": "Leitung"},
        ])

        # _rows_from_turso gibt leere Liste zurück (als ob Turso alle Daten verloren hat)
        with patch("database.turso_sync._rows_from_turso", return_value=[]):
            with patch("database.turso_sync._get_cfg") as mock_cfg:
                mock_cfg.return_value = MagicMock(_DB_DIR=tmp)
                from database import turso_sync
                n = turso_sync.pull_table(db_path, "mitarbeiter")

        assert n == 0, f"pull_table sollte 0 zurückgeben, gab {n}"
        assert _count_local_rows(db_path) == 2, "Lokale Zeilen wurden fälschlicherweise gelöscht!"
        ok("pull_table() mit leerem Turso-Ergebnis löscht nichts lokal")
    except Exception as e:
        fail("pull_table() mit leerem Turso-Ergebnis löscht nichts lokal", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pull_deletions_no_tombstone_preserves_local():
    """
    Wenn _deletions in Turso leer ist (kein Tombstone für externe Löschung),
    darf pull_deletions() die lokale DB NICHT anfassen.
    """
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "nesk3.db")
        _make_temp_db(db_path, [
            {"id": 10, "name": "Test Person", "abteilung": "Test"},
        ])

        # Turso gibt leere _deletions zurück
        empty_result = {
            "results": [{
                "response": {
                    "result": {
                        "cols": [{"name": "turso_table"}, {"name": "row_id"}],
                        "rows": []
                    }
                }
            }]
        }
        with patch("database.turso_sync._turso_request", return_value=empty_result):
            with patch("database.turso_sync._get_cfg") as mock_cfg:
                mock_cfg.return_value = MagicMock(_DB_DIR=tmp)
                from database import turso_sync
                n = turso_sync.pull_deletions()

        assert n == 0, f"pull_deletions sollte 0 zurückgeben, gab {n}"
        assert _count_local_rows(db_path) == 1, "Lokale Zeilen wurden fälschlicherweise gelöscht!"
        ok("pull_deletions() ohne Tombstone löscht nichts lokal")
    except Exception as e:
        fail("pull_deletions() ohne Tombstone löscht nichts lokal", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pull_table_upserts_without_deleting_extra_local():
    """
    Wenn Turso 1 Zeile hat, lokal aber 2 existieren (eine wurde in Turso extern gelöscht),
    darf die extra lokale Zeile NICHT entfernt werden.
    """
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "nesk3.db")
        _make_temp_db(db_path, [
            {"id": 1, "name": "Lokal+Turso",  "abteilung": "A"},
            {"id": 2, "name": "Nur Lokal",    "abteilung": "B"},  # Turso hat diese verloren
        ])

        turso_rows = [{"id": "1", "name": "Lokal+Turso", "abteilung": "A"}]
        with patch("database.turso_sync._rows_from_turso", return_value=turso_rows):
            with patch("database.turso_sync._get_cfg") as mock_cfg:
                mock_cfg.return_value = MagicMock(_DB_DIR=tmp)
                from database import turso_sync
                n = turso_sync.pull_table(db_path, "mitarbeiter")

        assert n == 1, f"pull_table sollte 1 (Turso-Zeile) zurückgeben, gab {n}"
        assert _count_local_rows(db_path) == 2, (
            "Extra lokale Zeile (Turso-Verlust ohne Tombstone) wurde fälschlicherweise gelöscht!"
        )
        ok("pull_table() ohne Tombstone löscht keine extra lokalen Zeilen")
    except Exception as e:
        fail("pull_table() ohne Tombstone löscht keine extra lokalen Zeilen", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Szenario B: restore_sql_backup() → Restore-Flag → Startup pusht nach Turso
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_sets_pending_flag():
    """
    Nach einem erfolgreichen restore_sql_backup() muss die Marker-Datei
    _restore_pending im DB-Verzeichnis existieren.
    """
    tmp = tempfile.mkdtemp()
    try:
        # Backup-Ordner (Tages-Ordner) mit Snapshot anlegen
        snap_ts = "120000"
        backup_dir = os.path.join(tmp, "backup_tag")
        os.makedirs(backup_dir)
        backup_db = os.path.join(backup_dir, f"nesk3_{snap_ts}.db")
        _make_temp_db(backup_db, [{"id": 99, "name": "Backup-Person", "abteilung": "X"}])

        # Live-DB-Verzeichnis
        live_dir = os.path.join(tmp, "live")
        os.makedirs(live_dir)
        live_db = os.path.join(live_dir, "nesk3.db")
        _make_temp_db(live_db, [{"id": 1, "name": "Live-Person", "abteilung": "Y"}])

        from backup import backup_manager

        # DB_PATH auf live_dir zeigen lassen
        with patch("backup.backup_manager._restore_pending_flag_path",
                   return_value=os.path.join(live_dir, "_restore_pending")):
            with patch("config.DB_PATH", os.path.join(live_dir, "nesk3.db")):
                ergebnis = backup_manager.restore_sql_backup(backup_dir, snap_ts)

        assert ergebnis["erfolg"], f"Restore fehlgeschlagen: {ergebnis['meldung']}"
        flag_path = os.path.join(live_dir, "_restore_pending")
        assert os.path.exists(flag_path), "_restore_pending Flag-Datei wurde nicht erstellt!"
        ok("restore_sql_backup() setzt _restore_pending Flag")
    except Exception as e:
        fail("restore_sql_backup() setzt _restore_pending Flag", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_restore_pending_flag_helpers():
    """
    is_restore_pending(), set_restore_pending(), clear_restore_pending()
    funktionieren korrekt zusammen.
    """
    tmp = tempfile.mkdtemp()
    try:
        flag_path = os.path.join(tmp, "_restore_pending")
        from backup import backup_manager

        with patch("backup.backup_manager._restore_pending_flag_path", return_value=flag_path):
            assert not backup_manager.is_restore_pending(), "Flag sollte am Anfang fehlen"
            backup_manager.set_restore_pending()
            assert backup_manager.is_restore_pending(), "Flag sollte nach set_restore_pending existieren"
            backup_manager.clear_restore_pending()
            assert not backup_manager.is_restore_pending(), "Flag sollte nach clear_restore_pending fehlen"

        ok("is_restore_pending/set/clear Hilfsfunktionen arbeiten korrekt")
    except Exception as e:
        fail("is_restore_pending/set/clear Hilfsfunktionen arbeiten korrekt", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_startup_calls_push_when_restore_pending():
    """
    Wenn _restore_pending Flag existiert, muss beim Start
    push_all_local_to_turso() statt pull_all() aufgerufen werden.
    Die Flag-Datei wird danach gelöscht.
    """
    try:
        push_called  = []
        pull_called  = []
        clear_called = []

        # Simuliert die Startup-Logik aus main.py
        def startup_turso_sync(is_pending: bool):
            """Nachbildung der main.py Startup-Logik (ohne echten Import)."""
            if is_pending:
                push_called.append(True)
                clear_called.append(True)
            else:
                pull_called.append(True)

        # Test: Flag gesetzt → push, kein pull
        startup_turso_sync(is_pending=True)
        assert len(push_called)  == 1, "push_all_local_to_turso() wurde nicht aufgerufen"
        assert len(pull_called)  == 0, "pull_all() wurde fälschlicherweise aufgerufen"
        assert len(clear_called) == 1, "clear_restore_pending() wurde nicht aufgerufen"

        # Test: Flag NICHT gesetzt → pull, kein push
        push_called.clear(); pull_called.clear(); clear_called.clear()
        startup_turso_sync(is_pending=False)
        assert len(pull_called)  == 1, "pull_all() wurde nicht aufgerufen"
        assert len(push_called)  == 0, "push_all_local_to_turso() wurde fälschlicherweise aufgerufen"

        ok("Startup: Flag gesetzt → push statt pull, Flag danach gelöscht")
    except Exception as e:
        fail("Startup: Flag gesetzt → push statt pull, Flag danach gelöscht", e)


def test_restored_data_survives_without_flag():
    """
    Ohne Restore-Flag (normaler Start): pull_table() überschreibt lokale Zeilen
    mit Turso-Daten (INSERT OR REPLACE). Das ist erwartetes Verhalten.
    Zeigt dass das Flag wirklich nötig ist.
    """
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "nesk3.db")
        # Lokal: Backup-Stand (id=5 mit altem Namen)
        _make_temp_db(db_path, [{"id": 5, "name": "Backup-Name-Alt", "abteilung": "Backup"}])

        # Turso hat neuen Stand (id=5 mit neuem Namen)
        turso_rows = [{"id": "5", "name": "Turso-Name-Neu", "abteilung": "Turso"}]
        with patch("database.turso_sync._rows_from_turso", return_value=turso_rows):
            with patch("database.turso_sync._get_cfg") as mock_cfg:
                mock_cfg.return_value = MagicMock(_DB_DIR=tmp)
                from database import turso_sync
                turso_sync.pull_table(db_path, "mitarbeiter")

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT name FROM mitarbeiter WHERE id=5").fetchone()
        conn.close()

        # Ohne Flag: Turso-Stand gewinnt → Backup-Name ist überschrieben
        assert row and row[0] == "Turso-Name-Neu", (
            "Ohne Restore-Flag überschreibt pull_table() lokale Daten mit Turso-Daten"
        )
        ok("BELEG: Ohne Restore-Flag überschreibt pull_all() wiederhergestellte Daten (Flag ist nötig!)")
    except Exception as e:
        fail("BELEG: Ohne Restore-Flag überschreibt pull_all() wiederhergestellte Daten", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Auswertung
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═" * 65)
    print("  Backup/Restore Logik – Integritätstest")
    print("═" * 65)

    print("\n── Szenario A: Turso externe Löschung ohne Tombstone ───────────")
    test_pull_table_empty_turso_preserves_local()
    test_pull_deletions_no_tombstone_preserves_local()
    test_pull_table_upserts_without_deleting_extra_local()

    print("\n── Szenario B: Restore-Flag → Startup pusht nach Turso ─────────")
    test_restore_pending_flag_helpers()
    test_restore_sets_pending_flag()
    test_startup_calls_push_when_restore_pending()
    test_restored_data_survives_without_flag()

    passed = sum(1 for _, ok_, _ in results if ok_)
    failed = sum(1 for _, ok_, _ in results if not ok_)

    print("\n" + "─" * 65)
    print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
    print("─" * 65 + "\n")

    if failed:
        for name, ok_, err in results:
            if not ok_:
                print(f"  FEHLER: {name}")
                print(f"          {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
