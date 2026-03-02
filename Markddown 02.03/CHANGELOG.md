# Changelog – Nesk3

Alle Änderungen in chronologischer Reihenfolge.

---

## 02.03.2026 – v3.1.1

### Stellungnahmen Dateien-Tab: Art + Mitarbeiter Spalten

#### `_datei_filter_changed()` (gui/mitarbeiter_dokumente.py)
- Bei Kategorie „Stellungnahmen": Tabelle wechselt auf **5 Spalten**
  - `Dateiname | Art | Mitarbeiter | Zuletzt geändert | Typ`
- Art + Mitarbeiter werden per `db_lade_alle()` aus der SQLite-DB nachgeschlagen
  - Lookup-Key: Dateiname (`os.path.basename(pfad_intern)`)
  - Falls kein DB-Eintrag vorhanden: zeigt `—`
- Für alle anderen Kategorien bleiben 3 Spalten (`Dateiname | Zuletzt geändert | Typ`)
- Spaltenbreiten: Dateiname Stretch, alle anderen ResizeToContents

#### `_table_kontextmenu()` (gui/mitarbeiter_dokumente.py)
- Rechtsklick-Menü erweitert um (nach Separator):
  - `✏  Bearbeiten` → ruft `_dokument_bearbeiten()` auf
  - `🔤  Umbenennen` → ruft `_dokument_umbenennen()` auf
  - `🗑  Löschen` → ruft `_dokument_loeschen()` auf
- Zeile wird vor Menu-Öffnen via `setCurrentCell(row, 0)` selektiert

---

## 02.03.2026 – v3.1.0

### Stellungnahmen: Assistent + Datenbank + lokale Web-Ansicht

#### `_StellungnahmeDialog` (gui/mitarbeiter_dokumente.py)
- Kontextabhängiger Dialog mit 3 Vorfall-Typen:
  - **Flug-Vorfall**: Flugnummer, Verspätungs-CB → Onblock/Offblock, Richtung (Inbound/Outbound/Beides), Inbound-Zeiten (Ankunft LFZ, Auftragsende), Outbound-Zeiten (Paxannahme-Zeit + Ort), Sachverhalt
  - **Passagierbeschwerde**: Onblock, Offblock, Sachverhalt, Beschwerdetext
  - **Nicht mitgeflogen**: Flugnummer + Sachverhalt
- Pflichtfeld-Validierung vor Speichern
- Speichert in ZWEI Pfaden: intern (`Daten/Mitarbeiterdokumente/Stellungnahmen/`) + extern (`97_Stellungnahmen/`)
- Word-Dokument mit DRK-Kopf-/Fußzeile, formatierte Abschnitte je Typ

#### `functions/stellungnahmen_db.py`
- SQLite-DB: `Daten/Mitarbeiterdokumente/Datenbank/stellungnahmen.db`
- Speichert Metadaten (kein Word-Inhalt): Mitarbeiter, Datum, Art, Flugnummer, alle Zeitfelder, Sachverhalt, Dateipfade
- `lade_alle(monat, jahr, art, suchtext)`, `verfuegbare_jahre()`, `eintrag_speichern()`, `eintrag_loeschen()`
- Automatischer DB-Eintrag nach `erstelle_stellungnahme()`
- HTML-Ansicht wird automatisch nach Save/Delete regeneriert

#### DB-Browser Tab (gui/mitarbeiter_dokumente.py)
- Tab „🔍 Datenbank-Suche" – nur sichtbar bei Kategorie "Stellungnahmen"
- Filter: Jahr, Monat, Art, Freitext (Mitarbeiter/Flugnummer/Sachverhalt)
- Tabelle: Datum, Mitarbeiter, Art, Flugnummer, Verfasst am, ID
- Aktionen: Dokument öffnen (intern→extern Fallback), Details, DB-Eintrag löschen

#### Lokale Web-Ansicht (`WebNesk/stellungnahmen_lokal.html`)
- Statische HTML-Seite – läuft ohne Server direkt per `file://`
- Generiert von `functions/stellungnahmen_html_export.py`  
- Volltextsuche, Filter (Jahr/Monat/Art), Detailansicht aller Felder
- Dateipfad-Anzeige + Copy-to-Clipboard
- URL-Hash-Navigation: `#id-42` springt direkt zu Datensatz 42
- Button „🌐 Web-Ansicht" in der App öffnet Seite im Standardbrowser

#### Übergabe-E-Mail Erweiterung (gui/uebergabe.py)
- Neues Optionsfeld „📋 Stellungnahmen-Link anhängen"
  - Allgemeiner Link zur HTML-Seite (`file:///...stellungnahmen_lokal.html`)
  - Optional: Direktverweis auf Einzelfall (`...html#id-42`)
  - Auswahl-ComboBox mit den letzten 30 Stellungnahmen

---

## 02.03.2026 – v3.0.0

### Mitarbeiter-Dokumente Widget

#### gui/main_window.py
- `NAV_ITEMS`: `("👥", "Mitarbeiter", 1)` eingefügt, alle Folge-Indizes +1
- Import + Stack: `MitarbeiterDokumenteWidget` an Index 1

#### gui/mitarbeiter_dokumente.py
- `MitarbeiterDokumenteWidget`: Titelleiste, Kategorieliste (6 Kat.), Dateitabelle
- Buttons: ＋ Neues Dokument · 📝 Stellungnahme · 📂 Öffnen · ✏ Bearbeiten · 🔤 Umbenennen · 🗑 Löschen
- `_NeuesDokumentDialog`, `_DokumentBearbeitenDialog`, `_StellungnahmeDialog`

#### functions/mitarbeiter_dokumente_functions.py
- `STELLUNGNAHMEN_EXTERN_PFAD` → `../97_Stellungnahmen/`
- `erstelle_stellungnahme(daten)` → `(intern_pfad, extern_pfad)`
- `erstelle_dokument_aus_vorlage()`, `lade_dokumente_nach_kategorie()`

#### Fahrzeuge
- `aktualisiere_status_eintrag(id, status, von, bis, grund)` in fahrzeug_functions.py
- `_StatusBearbeitenDialog` + Doppelklick-Support in gui/fahrzeuge.py

#### Dienstplan
- `_DispoZeitenVorschauDialog`: 6-spaltig, manuell bearbeitbar
- `round_dispo=True/False` Parameter in DienstplanParser
- `manuell_geaendert`-Flag verhindert erneutes Runden beim Export

---

## 26.02.2026 – v2.9.x

| Version | Inhalt |
|---------|--------|
| v2.9.4 | Info-Boxen + Tooltips gesamte App, HilfeDialog (Module/Workflow/FAQ/Anleitungen) |
| v2.9.3 | HilfeDialog Animationen (Fade+Slide-In, Puls, Laufbanner) |
| v2.9.1/2 | Tooltips alle Module, HilfeDialog 4 Tabs |

---

## 26.02.2026 – v2.8

- Dashboard: `_SkyWidget` QPainter-Animation (~33 FPS)
- Code-19: `_PocketWatchWidget` Taschenuhr mit Echtzeit-Zeigern
- Aufgaben Nacht: Tab „📋 Code 19 Mail"
- Sonderaufgaben + Einstellungen: E-Mobby-Fahrerkennung und -Verwaltung

---

## 25.02.2026 – v2.7

- Backup: `backup_manager.py` – ZIP-Backup/Restore
- Dienstplan: Krank-Aufschlüsselung (Tag/Nacht/Sonder), Dispo-Abschnitt-Tracking
- Statuszeile: Betreuer/Dispo-Trennung nach Schichttyp

---

## Backups

| Datei | Datum | Größe |
|-------|-------|-------|
| `Nesk3_backup_20260302_170729.zip` | 02.03.2026 17:07 | ~10 MB |
| `Nesk3_backup_20260302_151916.zip` | 02.03.2026 15:19 | ~10 MB |
| `Nesk3_backup_20260302_150415.zip` | 02.03.2026 15:04 | ~10 MB |
| `Nesk3_backup_20260302_144548.zip` | 02.03.2026 14:45 | ~10 MB |
| `Nesk3_backup_20260225_222303.zip` | 25.02.2026 22:23 | 8,3 MB |
