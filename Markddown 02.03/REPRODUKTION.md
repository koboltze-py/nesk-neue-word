# Nesk3 – Reproduktionsprotokoll

**Stand:** 02.03.2026 – v3.1.1

---

## Voraussetzungen

| Komponente | Version |
|-----------|---------|
| Python | 3.13+ |
| PySide6 | aktuell |
| openpyxl | aktuell |
| python-docx | aktuell |
| pywin32 | aktuell (Outlook) |

```powershell
pip install PySide6 openpyxl python-docx pywin32
```

---

## Projektstruktur

```
Nesk3/
├── main.py, config.py
├── gui/
│   ├── main_window.py, dashboard.py, mitarbeiter_dokumente.py
│   ├── uebergabe.py, fahrzeuge.py, dienstplan.py, ...
├── functions/
│   ├── mitarbeiter_dokumente_functions.py
│   ├── stellungnahmen_db.py
│   ├── stellungnahmen_html_export.py
│   └── ...
├── database/ (connection.py, migrations.py, models.py)
├── backup/ (backup_manager.py)
├── WebNesk/
│   ├── stellungnahmen_lokal.html   ← generiert, kein Server nötig
│   └── ...
└── Daten/
    └── Mitarbeiterdokumente/
        ├── Stellungnahmen/, Bescheinigungen/, ...
        ├── Datenbank/stellungnahmen.db
        └── Mitarbeiter Vorlagen/Kopf und Fußzeile/...docx
```

---

## Datenbank initialisieren

```python
from database.migrations import run_migrations
run_migrations()
```

Die Stellungnahmen-DB wird automatisch beim ersten Aufruf von `stellungnahmen_db.py` erstellt.

---

## Anwendung starten

```powershell
python main.py
```

---

## Stellungnahmen-Web-Ansicht

Die HTML-Datei `WebNesk/stellungnahmen_lokal.html` wird automatisch generiert.
Manuell regenerieren:

```python
from functions.stellungnahmen_html_export import generiere_html
generiere_html()
```

Browser-Aufruf: `file:///C:/...Nesk3/WebNesk/stellungnahmen_lokal.html`
Direktlink zu Datensatz 42: `...html#id-42`

---

## Bekannte Probleme

| Problem | Lösung |
|---------|--------|
| PySide6 nicht installierbar | System-Python nutzen |
| Outlook-Mail nicht erstellt | pywin32 installieren, Outlook öffnen |
| Vorlage nicht gefunden | Pfad in mitarbeiter_dokumente_functions.py prüfen |
| HTML-Seite leer | Noch keine Stellungnahmen angelegt oder generiere_html() aufrufen |

---

## Backup erstellen

```powershell
cd "Nesk3"
python -c "
import os, zipfile
from datetime import datetime
BASE_DIR = os.getcwd()
BACKUP_DIR = os.path.join(BASE_DIR, 'Backup Data')
EXCLUDE = {'__pycache__', '.git', 'Backup Data', 'backup', 'build_tmp', 'Exe'}
os.makedirs(BACKUP_DIR, exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
zip_path = os.path.join(BACKUP_DIR, f'Nesk3_backup_{stamp}.zip')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for fname in files:
            full = os.path.join(root, fname)
            try:
                zf.write(full, os.path.relpath(full, BASE_DIR))
            except (PermissionError, OSError):
                pass
print('Backup:', zip_path)
"
```
