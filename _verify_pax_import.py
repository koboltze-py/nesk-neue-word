"""
Verification script - Check if PAX data was imported correctly
"""
from database.pax_db import lade_tages_pax, lade_alle_eintraege

# Check some specific dates
test_dates = [
    "2026-01-02",  # Should be 236
    "2026-02-14",  # Should be 248
    "2026-03-01",  # Should be 191
    "2026-03-29",  # Should be 288
    "2026-03-31",  # Should be 274
]

print("="*80)
print("PAX-Daten Verifikation")
print("="*80)

for datum in test_dates:
    pax = lade_tages_pax(datum)
    print(f"{datum}: PAX = {pax}")

print("\n" + "="*80)
print("März 2026 - Alle Einträge")
print("="*80)

eintraege = lade_alle_eintraege(2026)
maerz_eintraege = [e for e in eintraege if e['datum'].startswith('2026-03')]

print(f"Anzahl Einträge im März: {len(maerz_eintraege)}")
print("\nErste 5 Einträge:")
for e in sorted(maerz_eintraege, key=lambda x: x['datum'])[:5]:
    print(f"  {e['datum']}: PAX = {e['pax_zahl']}, SL-Einsätze = {e['einsaetze_zahl']}")

print("\nLetzte 5 Einträge:")
for e in sorted(maerz_eintraege, key=lambda x: x['datum'])[-5:]:
    print(f"  {e['datum']}: PAX = {e['pax_zahl']}, SL-Einsätze = {e['einsaetze_zahl']}")
