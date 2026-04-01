"""
Test der PAX-Extraktion auf einem einzelnen Dokument
"""
import os
import re
from datetime import datetime
from docx import Document

TEST_DOC = r"C:\Users\DRKairport\OneDrive - Deutsches Rotes Kreuz - Kreisverband Köln e.V\Dateien von Erste-Hilfe-Station-Flughafen - DRK Köln e.V_ - !Gemeinsam.26\06_Stärkemeldung\03_März\Stärkemeldung 01.03.2026 - 02.03.2026.docx"

def extrahiere_datum_aus_dateiname(dateiname: str) -> str:
    """Extrahiert das Von-Datum aus dem Dateinamen."""
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', dateiname)
    if match:
        tag, monat, jahr = match.groups()
        return f"{jahr}-{monat}-{tag}"
    return None

def extrahiere_pax_aus_dokument(doc_pfad: str) -> tuple[int, int]:
    """Extrahiert PAX-Zahl und SL-Einsätze aus einem Word-Dokument."""
    try:
        doc = Document(doc_pfad)
        
        pax_zahl = None
        sl_einsaetze = None
        
        # Durchsuche die letzten 30 Absätze von unten nach oben
        for para in reversed(doc.paragraphs[-30:]):
            text = para.text.strip()
            
            # Suche nach PAX-Zahl im Format "- 191 -"
            if pax_zahl is None:
                match = re.search(r'-\s*(\d+)\s*-', text)
                if match:
                    pax_zahl = int(match.group(1))
                    print(f"PAX gefunden: {pax_zahl} in Zeile: '{text}'")
                    continue
            
            # Suche nach SL-Einsätze (optional)
            if sl_einsaetze is None:
                match = re.search(r'(?:SL[\s-]*)?Einsätze[\s:]+(\d+)', text, re.IGNORECASE)
                if match:
                    sl_einsaetze = int(match.group(1))
                    print(f"SL-Einsätze gefunden: {sl_einsaetze} in Zeile: '{text}'")
        
        return pax_zahl or 0, sl_einsaetze or 0
        
    except Exception as e:
        print(f"Fehler beim Lesen: {e}")
        return 0, 0


# Test
print(f"Test-Dokument: {os.path.basename(TEST_DOC)}\n")

dateiname = os.path.basename(TEST_DOC)
datum = extrahiere_datum_aus_dateiname(dateiname)
print(f"Extrahiertes Datum: {datum}")

pax_zahl, sl_einsaetze = extrahiere_pax_aus_dokument(TEST_DOC)
print(f"\nErgebnis:")
print(f"  PAX-Zahl: {pax_zahl}")
print(f"  SL-Einsätze: {sl_einsaetze}")
