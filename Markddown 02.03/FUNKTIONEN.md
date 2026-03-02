# Nesk3 – Vollständige Funktionsübersicht

**Stand:** 02.03.2026 – v3.1.1

---

## 1. Hauptfenster

### `gui/main_window.py` – `MainWindow`

| Index | Icon | Label |
|-------|------|-------|
| 0 | 🏠 | Dashboard |
| 1 | 👥 | Mitarbeiter |
| 2 | ☀️ | Aufgaben Tag |
| 3 | 🌙 | Aufgaben Nacht |
| 4 | 📅 | Dienstplan |
| 5 | 📋 | Übergabe |
| 6 | 🚗 | Fahrzeuge |
| 7 | 🕐 | Code 19 |
| 8 | 🖨️ | Ma. Ausdrucke |
| 9 | 🤒 | Krankmeldungen |
| 10 | 💾 | Backup |
| 11 | ⚙️ | Einstellungen |

---

## 2. Mitarbeiter-Dokumente

### `gui/mitarbeiter_dokumente.py` – `MitarbeiterDokumenteWidget`

**Aufbau:**
- Titelleiste (blau): „📂 Ordner öffnen" + „🔄 Refresh"
- Linke Sidebar: Kategorieliste mit Dateianzahl-Badge + Vorlage-Status
- Rechter Bereich: QTabWidget
  - Tab 0 „📂 Dateien": Aktions-Buttons + Dateitabelle
  - Tab 1 „🔍 Datenbank-Suche": Filter + DB-Tabelle (nur bei Kategorie Stellungnahmen)

**Aktions-Buttons:**

| Button | Sichtbar | Funktion |
|--------|----------|----------|
| ＋ Neues Dokument | immer | `_NeuesDokumentDialog` |
| 📝 Stellungnahme | nur Stellungnahmen | `_StellungnahmeDialog` |
| 📂 Öffnen | immer | OS-Standard |
| ✏ Bearbeiten | immer | `_DokumentBearbeitenDialog` |
| 🔤 Umbenennen | immer | `QInputDialog` |
| 🗑 Löschen | immer | dauerhaft mit Bestätigung |
| 🌐 Web-Ansicht | nur Stellungnahmen | Browser öffnet `stellungnahmen_lokal.html` |

**Dateitabelle – Spalten:**

| Kategorie | Spalten |
|-----------|---------|
| Alle anderen | Dateiname · Zuletzt geändert · Typ |
| Stellungnahmen | Dateiname · **Art** · **Mitarbeiter** · Zuletzt geändert · Typ |

Art und Mitarbeiter werden aus der SQLite-DB per Dateiname nachgeschlagen. Kein DB-Eintrag → `—`.

**Rechtsklick-Menü (Dateitabelle):**

| Aktion | Funktion |
|--------|---------|
| 📂 Im Explorer anzeigen | Explorer mit Dateiauswahl |
| 📄 Öffnen | OS-Standard öffnen |
| *(Separator)* | |
| ✏ Bearbeiten | `_DokumentBearbeitenDialog` |
| 🔤 Umbenennen | `QInputDialog` |
| 🗑 Löschen | dauerhaft mit Bestätigung |

**`_StellungnahmeDialog`:**
- Scrollbarer Dialog, kontextabhängige Felder je Art
- Pflichtvalidierung: Mitarbeiter, Flugnummer (bei Flug/NM), Sachverhalt

**DB-Browser:**
- Filter: Jahr-CB, Monat-CB, Art-CB, Freitext-QLineEdit
- Treffer-Label, Reset-Button
- Tabelle: Datum Vorfall, Mitarbeiter, Art, Flugnummer, Verfasst am, ID
- Doppelklick: Dokument öffnen
- Buttons: 📂 Dokument öffnen, 🔎 Details, 🗑 DB-Eintrag löschen

---

## 3. `functions/mitarbeiter_dokumente_functions.py`

| Symbol | Beschreibung |
|--------|-------------|
| `VORLAGE_PFAD` | Pfad zur DRK-Kopf-/Fußzeile-Vorlage |
| `DOKUMENTE_BASIS` | `Daten/Mitarbeiterdokumente/` |
| `STELLUNGNAHMEN_EXTERN_PFAD` | `...\97_Stellungnahmen\` |
| `KATEGORIEN` | Liste der 6 Kategorien |
| `sicherungsordner()` | Legt Basis + Unterordner an |
| `lade_dokumente_nach_kategorie()` | `{kat: [{name, pfad, geaendert}]}` |
| `erstelle_dokument_aus_vorlage()` | Word-Dokument aus DRK-Vorlage |
| `erstelle_stellungnahme(daten)` | Word + DB-Eintrag → `(intern, extern)` |
| `oeffne_datei(pfad)` | Windows `start` |
| `loesche_dokument(pfad)` | Sicheres Löschen |
| `umbenennen_dokument(alt, neu)` | Umbenennen |

---

## 4. `functions/stellungnahmen_db.py`

| Funktion | Beschreibung |
|----------|-------------|
| `eintrag_speichern(daten, intern, extern)` | Neuen Datensatz anlegen → ID |
| `eintrag_loeschen(id)` | Datensatz entfernen (Datei bleibt) |
| `lade_alle(monat, jahr, art, suchtext)` | Gefilterte Abfrage |
| `verfuegbare_jahre()` | Jahre mit Einträgen (absteigend) |
| `verfuegbare_monate(jahr)` | Monate im Jahr mit Einträgen |
| `get_eintrag(id)` | Einzelnen Datensatz abrufen |

---

## 5. `functions/stellungnahmen_html_export.py`

| Funktion | Beschreibung |
|----------|-------------|
| `generiere_html()` | Liest DB, schreibt `WebNesk/stellungnahmen_lokal.html` |
| `html_pfad()` | Gibt absoluten Pfad der HTML-Datei zurück |

---

## 6. Dienstplan

### `gui/dienstplan.py` – `DienstplanWidget`
- Excel laden, farbcodierte HTML-Tabelle
- Statuszeile: Tagdienst/Nachtdienst/Krank, getrennt nach Betreuer/Dispo
- `_DispoZeitenVorschauDialog`: Vergleich Excel vs. Export, manuelle Bearbeitung

### `functions/dienstplan_parser.py`
- `round_dispo=True/False`
- `parse()`: inkl. Krank-Klassifizierung und Dispo-Abschnitt-Tracking

---

## 7. Übergabe

### `gui/uebergabe.py` – `UebergabeWidget`
- Tagdienst/Nachtdienst-Button, automatische Zeiten
- Speichern · Abschließen · E-Mail-Entwurf · Löschen
- `_email_erstellen()`: Protokолл + Fahrzeuge + Schäden + Handys
  - **NEU:** Sektion „Stellungnahmen-Link" mit ComboBox für Fallverweis

---

## 8. Fahrzeuge

### `gui/fahrzeuge.py` – `FahrzeugeWidget`
- Status-Tab: aktuell + Verlauf; `_StatusBearbeitenDialog` (Doppelklick oder ✏)
- Schäden-Tab, Termine-Tab, Historie-Tab

### `functions/fahrzeug_functions.py`
- `aktualisiere_status_eintrag(id, status, von, bis, grund)`
- `setze_fahrzeug_status()`, `lade_status_historie()`, `aktueller_status()`

---

## 9. Datenbank (SQLite)

### Haupt-DB (`nesk3.db`) – `database/`
| Tabelle | Inhalt |
|---------|--------|
| `mitarbeiter` | name, kuerzel, funktion, export_flag |
| `fahrzeuge` | kennzeichen, bezeichnung, typ |
| `fahrzeug_status` | status, von, bis, grund |
| `fahrzeug_schaeden` | datum, beschreibung, schwere |
| `fahrzeug_termine` | titel, faellig_am, erledigt |
| `uebergabe_protokolle` | schicht_typ, beginn, ende, inhalt, status |
| `settings` | key, value |

### Stellungnahmen-DB (`stellungnahmen.db`) – eigene SQLite-Datei
Siehe Abschnitt 4 (stellungnahmen_db.py).

---

## 10. Backup-System

- `create_zip_backup()` → `Backup Data/Nesk3_backup_YYYYMMDD_HHMMSS.zip`
- `list_zip_backups()`, `restore_from_zip(zip_path)`
- Ausgeschlossen: `__pycache__`, `.git`, `Backup Data`, `backup`, `build_tmp`, `Exe`
