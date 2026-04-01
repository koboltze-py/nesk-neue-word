"""
Setzt die Schulungen-Datenbank zurück und importiert frisch aus Excel.
"""
import sqlite3
from pathlib import Path

DB = Path("database SQL/schulungen.db")

# Alle Schulungsdaten löschen (Tabellen leeren, nicht droppen)
conn = sqlite3.connect(DB)
conn.execute("DELETE FROM schulungseintraege")
conn.execute("DELETE FROM mitarbeiter")
conn.execute("DELETE FROM schulungen_manuell")
conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('mitarbeiter','schulungseintraege','schulungen_manuell')")
conn.commit()
conn.close()
print("DB geleert.")

# Neu importieren
from functions.schulungen_db import excel_importieren, _dedup_schulungseintraege
imp, skip = excel_importieren()
print(f"Importiert: {imp}  Übersprungen: {skip}")

_dedup_schulungseintraege()
print("Dedup fertig.")

# Kurze Prüfung
conn2 = sqlite3.connect(DB)
conn2.row_factory = sqlite3.Row
rows = conn2.execute(
    "SELECT m.nachname, s.schulungstyp, s.datum_absolviert, s.gueltig_bis, s.status"
    " FROM schulungseintraege s JOIN mitarbeiter m ON m.id=s.mitarbeiter_id"
    " WHERE s.schulungstyp IN ('EH','Refresher') AND s.status='abgelaufen'"
    " ORDER BY s.gueltig_bis DESC LIMIT 15"
).fetchall()
print(f"\nNoch als abgelaufen markierte EH/Refresher ({len(rows)} gesamt, zeige max 15):")
for r in rows:
    print(f"  {r['nachname']:<22} {r['schulungstyp']:<10} absolviert:{r['datum_absolviert']:<13} gueltig_bis:{r['gueltig_bis']}")
conn2.close()
