import sqlite3
from pathlib import Path

db = Path("database SQL/schulungen.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT m.nachname, m.vorname, s.schulungstyp, s.datum_absolviert, s.gueltig_bis, s.status"
    " FROM schulungseintraege s"
    " JOIN mitarbeiter m ON m.id = s.mitarbeiter_id"
    " WHERE s.schulungstyp IN ('EH', 'Refresher')"
    " ORDER BY s.gueltig_bis ASC LIMIT 30"
).fetchall()

print(f"{'Name':<22} {'Typ':<10} {'Absolviert':<13} {'Gueltig bis':<13} Status")
print("-" * 75)
for r in rows:
    print(f"{r['nachname']:<22} {r['schulungstyp']:<10} {r['datum_absolviert'] or '--':<13} {r['gueltig_bis'] or '--':<13} {r['status']}")

conn.close()
