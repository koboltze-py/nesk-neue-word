"""
Dokument-Archiv
===============
Kopiert fertig gespeicherte Dokumente automatisch in einen zentralen
Archivordner, strukturiert nach Funktion.

Zielordner (Basis):
    Backup Data/Dokumente/

Unterordner je Funktion:
    Stärkemeldung/         – Word-Stärkemeldungen (Dienstplan-Export)
    Stellungnahmen/        – Stellungnahme-Dokumente (Word)
    Dienstanweisungen/     – Dienstanweisungen (Word)
    Mitarbeiterdokumente/  – Allgemeine Mitarbeiterdokumente (Word)
    Verspätung/            – Verspätungs-Protokolle FO_CGN_27 (Word)
    Patienten_Word/        – Patientenprotokoll-Einzelblätter (Word)
    Patienten_Excel/       – Patienten-Sammel-Export (Excel)
    Einsatzprotokoll/      – Einsatzprotokoll-Export (Excel)
    Sonderaufgaben/        – Sonderaufgaben-Tagesblätter (Excel)

Verwendung:
    from functions.dokument_archiv import kopiere_ins_archiv
    kopiere_ins_archiv(pfad_zur_datei, "stellungnahmen")

Fehler werden grundsätzlich ignoriert – das Original-Speichern
wird dadurch niemals unterbrochen.
"""
import shutil
from pathlib import Path

from config import BASE_DIR

_ARCHIV_BASIS = Path(BASE_DIR) / "Backup Data" / "Dokumente"

_UNTERORDNER: dict[str, str] = {
    "staerkemeldung":      "Stärkemeldung",
    "stellungnahmen":      "Stellungnahmen",
    "dienstanweisungen":   "Dienstanweisungen",
    "mitarbeiterdokumente": "Mitarbeiterdokumente",
    "verspaetung":         "Verspätung",
    "patienten_word":      "Patienten_Word",
    "patienten_excel":     "Patienten_Excel",
    "einsatzprotokoll":    "Einsatzprotokoll",
    "sonderaufgaben":      "Sonderaufgaben",
}


def kopiere_ins_archiv(quell_pfad: str, bereich: str) -> None:
    """
    Kopiert *quell_pfad* in den Archivordner des angegebenen Bereichs.

    Args:
        quell_pfad: Absoluter Pfad zur soeben gespeicherten Datei.
        bereich:    Schlüssel aus _UNTERORDNER (z. B. ``'stellungnahmen'``).
                    Unbekannte Schlüssel werden als Ordnername verwendet.

    Fehler werden stillschweigend ignoriert.
    """
    try:
        ordner_name = _UNTERORDNER.get(bereich, bereich)
        ziel_ordner = _ARCHIV_BASIS / ordner_name
        ziel_ordner.mkdir(parents=True, exist_ok=True)
        ziel_datei = ziel_ordner / Path(quell_pfad).name
        shutil.copy2(quell_pfad, ziel_datei)
    except Exception:
        pass  # Archivfehler blockiert niemals den Original-Workflow
