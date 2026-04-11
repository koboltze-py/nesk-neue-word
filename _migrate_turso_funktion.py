"""Einmalige Migration: funktion-Werte in Turso auf neue Bezeichner aktualisieren."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.turso_sync import _turso_request

print("Prüfe Turso-Daten …")

# Zeilen mit alten Werten ermitteln
result = _turso_request(
    "SELECT id, funktion FROM ma__mitarbeiter WHERE funktion IN ('stamm', 'dispo')"
)
rows = result["results"][0]["response"]["result"]["rows"]
print(f"Gefunden: {len(rows)} Zeilen mit alten Werten")

if not rows:
    print("Nichts zu tun.")
    sys.exit(0)

KARTE = {"stamm": "Schichtleiter", "dispo": "Dispo"}
for row in rows:
    ma_id   = row[0]["value"]
    funk_alt = row[1]["value"]
    funk_neu = KARTE.get(funk_alt, "Schichtleiter")
    _turso_request(
        "UPDATE ma__mitarbeiter SET funktion = ? WHERE id = ?",
        [funk_neu, ma_id]
    )
    print(f"  ID {ma_id}: '{funk_alt}' → '{funk_neu}'")

print("Turso-Migration abgeschlossen.")
