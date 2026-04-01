# -*- coding: utf-8 -*-
# Batch-Test: Dashboard-Word-Export fuer alle Maerz-Tagesdienstplaene.
# Ausgabe: Desktop\bei\neuneu
import os, sys, random
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_OD = r"C:\Users\DRKairport\OneDrive - Deutsches Rotes Kreuz - Kreisverband Köln e.V"
QUELL_ORDNER = (
    _OD + r"\Dateien von Erste-Hilfe-Station-Flughafen - DRK Köln e.V_ - !Gemeinsam.26"
    r"\04_Tagesdienstpläne\03_März"
)
ZIEL_ORDNER = _OD + r"\Desktop\bei\neuneu"
os.makedirs(ZIEL_ORDNER, exist_ok=True)

# ── Fiktive Schichtleiterdaten ────────────────────────────────────────────────
SL_TAG_NAMEN   = ["Lars Peters", "Kai Hoffmann", "Nina Schulze", "Tom Brandt",
                  "Sara Mayer",  "Felix Wagner", "Jana Richter", "Marc Simon"]
SL_NACHT_NAMEN = ["Petra Koch",  "Stefan Bauer", "Lena Fischer", "Dirk Müller",
                  "Anja Weber",  "Oliver Klein", "Tanja Vogel",  "Ben Schmitt"]

random.seed(42)

def zufalls_pax(tag: int) -> int:
    """Simuliert realistische PAX-Zahlen für KCG (30.000–55.000)."""
    basis = 38_000 if tag % 7 in (5, 6) else 32_000   # Wochenende etwas mehr
    return basis + random.randint(-4000, 8000)

def zufalls_einsaetze(tag: int) -> int:
    return random.randint(2, 14)

def zufalls_bulmor() -> int:
    return random.choices([3, 4, 5, 5, 5], weights=[1, 2, 6, 6, 6])[0]

# ── Hauptlauf ─────────────────────────────────────────────────────────────────
from functions.dienstplan_parser import DienstplanParser
from functions.staerkemeldung_dashboard_export import StaerkemeldungDashboardExport

excel_dateien = sorted(Path(QUELL_ORDNER).glob("*.xlsx"))
print(f"\n{len(excel_dateien)} Excel-Dateien gefunden – starte Export ...\n")

ok = 0; fehler = 0

for xls in excel_dateien:
    # Datum aus Dateinamen parsen (DD.MM.YYYY.xlsx)
    try:
        datum = datetime.strptime(xls.stem, "%d.%m.%Y")
    except ValueError:
        print(f"  [SKIP] Kein Datum im Dateinamen: {xls.name}")
        continue

    tag = datum.day
    sl_tag   = SL_TAG_NAMEN[tag   % len(SL_TAG_NAMEN)]
    sl_nacht = SL_NACHT_NAMEN[tag % len(SL_NACHT_NAMEN)]
    pax      = zufalls_pax(tag)
    einsaetze= zufalls_einsaetze(tag)
    bulmor   = zufalls_bulmor()

    # Dienstplan parsen
    try:
        data = DienstplanParser(str(xls), alle_anzeigen=False).parse()
        if not data.get("success"):
            print(f"  [WARN] Parser-Fehler bei {xls.name}: {data.get('error','?')}")
            data = {"betreuer": [], "dispo": [], "kranke": []}
    except Exception as e:
        print(f"  [WARN] Exception beim Parsen von {xls.name}: {e}")
        data = {"betreuer": [], "dispo": [], "kranke": []}

    # Ausgabepfad
    ziel = os.path.join(ZIEL_ORDNER, f"Staerkemeldung_{datum.strftime('%Y-%m-%d')}.docx")

    # Export
    try:
        exp = StaerkemeldungDashboardExport(
            dienstplan_data        = data,
            ausgabe_pfad           = ziel,
            von_datum              = datum,
            bis_datum              = datum,
            pax_zahl               = pax,
            bulmor_aktiv           = bulmor,
            einsaetze_zahl         = einsaetze,
            sl_tag_name            = sl_tag,
            sl_nacht_name          = sl_nacht,
            stationsleitung        = "Lars Peters",
        )
        pfad, warnungen = exp.export()
        for w in warnungen:
            print(f"    [WARN] {w}")
        print(f"  [OK]  {datum.strftime('%d.%m.%Y')}  PAX={pax:>6,}  SL-Tag={sl_tag:<14}  SL-Nacht={sl_nacht}")
        ok += 1
    except Exception as e:
        print(f"  [FEHLER] {xls.name}: {e}")
        fehler += 1

print(f"\nFertig: {ok} OK, {fehler} Fehler")
print(f"Ausgabe: {ZIEL_ORDNER}\n")
