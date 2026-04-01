import sqlite3
conn = sqlite3.connect("database SQL/schulungen.db")
conn.row_factory = sqlite3.Row

# Check Chatziioannidis entries with IDs
rows = conn.execute(
    "SELECT se.id, se.mitarbeiter_id, m.nachname, m.vorname, se.schulungstyp, se.datum_absolviert, se.gueltig_bis "
    "FROM schulungseintraege se JOIN mitarbeiter m ON m.id=se.mitarbeiter_id "
    "WHERE m.nachname LIKE '%Chatzi%' OR m.nachname LIKE '%Charrat%'"
).fetchall()
print("Eintraege:")
for r in rows:
    print(dict(r))

# Count all EH/Refresher per MA by looking for same name
rows2 = conn.execute(
    "SELECT se.mitarbeiter_id, m.nachname, m.vorname, se.schulungstyp, COUNT(*) as n "
    "FROM schulungseintraege se JOIN mitarbeiter m ON m.id=se.mitarbeiter_id "
    "WHERE se.schulungstyp IN ('EH','Refresher') "
    "GROUP BY se.mitarbeiter_id, se.schulungstyp HAVING n > 1"
).fetchall()
print("\nDoppelte Eintraege pro MA+Typ:")
for r in rows2:
    print(dict(r))
conn.close()
