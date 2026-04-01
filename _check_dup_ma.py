import sqlite3
conn = sqlite3.connect("database SQL/schulungen.db")
rows2 = conn.execute(
    "SELECT nachname, vorname, COUNT(*) as n FROM mitarbeiter GROUP BY nachname, vorname HAVING n > 1"
).fetchall()
print("Doppelte MAs:")
for r in rows2:
    print(r)
conn.close()
