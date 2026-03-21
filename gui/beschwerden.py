"""
Beschwerden-Widget
Erfassung, Verwaltung und KI-gestützte Analyse von Beschwerden.

Quellen:  Freitext · Word-Datei (.docx) · PDF-Datei
Extras  : E-Mail-Extraktion · Namens-Extraktion · Anonymisierung
          · Gemini-KI-Analyse · Outlook-Antwort
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QDate, QEvent, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget, QHeaderView,
)

from config import FIORI_BLUE, FIORI_TEXT, GEMINI_API_KEY

from functions.beschwerden_db import (
    KATEGORIEN, PRIORITAETEN, QUELLEN, STATUS_OPTIONEN,
    antwort_speichern, beschwerde_aktualisieren, beschwerde_loeschen,
    beschwerde_speichern, lade_antworten, lade_beschwerde, lade_beschwerden,
)

# ── Gemini-Konfig ──────────────────────────────────────────────────────────────
# gemini-2.5-flash: Free-Tier-kompatibel (2.0-flash hat Quota-Sperre auf diesem Key)
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
)

# ── Farb-Mappings ──────────────────────────────────────────────────────────────
_PRIO_FARBEN = {
    "Niedrig":  ("#27ae60", "white"),
    "Mittel":   ("#e67e22", "white"),
    "Hoch":     ("#e74c3c", "white"),
    "Kritisch": ("#900000", "white"),
}
_STATUS_FARBEN = {
    "Offen":           ("#e74c3c", "white"),
    "In Bearbeitung":  ("#e67e22", "white"),
    "Erledigt":        ("#27ae60", "white"),
    "Abgewiesen":      ("#6c757d", "white"),
}

# ══════════════════════════════════════════════════════════════════════════════
#  Text-Verarbeitungs-Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def _extrahiere_aus_word(pfad: str) -> str:
    try:
        from docx import Document
        doc = Document(pfad)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "[Fehler: python-docx nicht installiert. 'pip install python-docx']"
    except Exception as e:
        return f"[Fehler beim Lesen der Word-Datei: {e}]"


def _extrahiere_aus_pdf(pfad: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(pfad)
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()
    except ImportError:
        return "[Fehler: pypdf nicht installiert. 'pip install pypdf']"
    except Exception as e:
        return f"[Fehler beim Lesen der PDF-Datei: {e}]"


def _extrahiere_emails(text: str) -> list[str]:
    pattern = r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
    seen: set[str] = set()
    result = []
    for m in re.finditer(pattern, text):
        e = m.group(0).lower()
        if e not in seen:
            seen.add(e)
            result.append(m.group(0))
    return result


def _extrahiere_namen(text: str) -> list[str]:
    """Einfache heuristische Namens-Extraktion aus deutschen Texten."""
    patterns = [
        r"(?:Von|From|Absender|Name|Mein Name(?: ist)?)\s*[:\-]\s*"
        r"([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)",
        r"(?:Mit freundlichen Grüßen|Freundliche Grüße|Hochachtungsvoll)"
        r"[\s,\r\n]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)",
        r"(?:Unterschrift|Beschwerdeführer)[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)",
        r"^([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\s*$",
    ]
    seen: set[str] = set()
    result = []
    for patt in patterns:
        for m in re.finditer(patt, text, re.IGNORECASE | re.MULTILINE):
            name = m.group(1).strip()
            if name and name not in seen and len(name) < 80:
                seen.add(name)
                result.append(name)
    return result


def _extrahiere_telefon(text: str) -> list[str]:
    """Erkennt Telefonnummern in deutschem Format (Festnetz + Mobil, Sonderformat)."""
    patterns = [
        r'\+49[\s\-\/]?(?:[\d][\s\-\/]?){9,14}',            # +49 ...
        r'\(0\d{2,5}\)[\s\-\/]?[\d][\s\-\/\d]{4,12}',       # (0xxx) xxx
        r'\b0\d{2,5}[\s\-\/]?[\d][\s\-\/\d]{3,12}\b',        # 0xxx xxxxxxx
    ]
    seen: set[str] = set()
    result = []
    for patt in patterns:
        for m in re.finditer(patt, text):
            raw = m.group(0).strip()
            normalized = re.sub(r'[\s\-\/]', '', raw)
            if len(normalized) >= 6 and normalized not in seen:
                seen.add(normalized)
                result.append(raw)
    return result


def _anonymisiere_text(
    text: str,
    emails: list[str],
    namen: list[str],
    telefone: list[str] | None = None,
    extra_begriffe: str = "",
) -> tuple[str, dict[str, str]]:
    """
    Ersetzt E-Mails, Namen, Telefonnummern und Extra-Begriffe durch Platzhalter.
    Ersetzt automatisch IBANs und Geburtsdaten (immer persönlich).
    Gibt (anonymisierter_text, mapping) zurück.
    """
    mapping: dict[str, str] = {}
    result = text

    for i, email in enumerate(emails, 1):
        ph = f"[EMAIL_{i}]"
        mapping[ph] = email
        result = result.replace(email, ph)

    for i, name in enumerate(namen, 1):
        ph = f"[PERSON_{i}]"
        mapping[ph] = name
        result = result.replace(name, ph)

    for i, tel in enumerate(telefone or [], 1):
        ph = f"[TEL_{i}]"
        mapping[ph] = tel
        result = result.replace(tel, ph)

    # Auto: IBANs (immer persönliche Finanzdaten)
    iban_idx = len(mapping) + 1
    for m in re.finditer(r'\b[A-Z]{2}\d{2}[\s\dA-Z]{12,30}\b', result):
        val = m.group(0).strip()
        if val not in mapping.values():
            ph = f"[IBAN_{iban_idx}]"
            mapping[ph] = val
            result = result.replace(val, ph)
            iban_idx += 1

    # Auto: Geburtsdaten (TT.MM.JJJJ mit Jahr 19xx oder 200x)
    geb_idx = 1
    for m in re.finditer(
        r'\b(\d{1,2})\.\s*(\d{1,2})\.\s*((?:19|200)\d{2})\b', result
    ):
        val = m.group(0)
        if val not in mapping.values():
            ph = f"[GEBURTSDATUM_{geb_idx}]"
            mapping[ph] = val
            result = result.replace(val, ph)
            geb_idx += 1

    for i, term in enumerate(
        [t.strip() for t in extra_begriffe.split("\n") if t.strip()], 1
    ):
        ph = f"[TERM_{i}]"
        mapping[ph] = term
        result = result.replace(term, ph)

    return result, mapping


def _call_gemini(anon_text: str, kontext: dict | None = None) -> str:
    """
    Sendet den anonymisierten Text an Gemini und gibt die Antwort zurück.
    kontext: {'laenge': str, 'ton': str, 'freitext': str}
    Bei HTTP 429 (Rate-Limit) wird bis zu 3x mit Wartezeit erneut versucht.
    """
    ctx = kontext or {}
    laenge  = ctx.get("laenge",   "Mittel (3–5 Absätze)")
    ton     = ctx.get("ton",     "Förmlich")
    freitext_ctx = (ctx.get("freitext", "") or "").strip()

    _laenge_map = {
        "Kurz (1–2 Absätze)":   "Halte jeden Abschnitt kurz (max. 2 Absätze).",
        "Mittel (3–5 Absätze)": "Halte jeden Abschnitt mittellang (3–5 Absätze).",
        "Lang (ausführlich)":    "Antworte ausführlich und detailliert.",
        "Sehr ausführlich":      "Antworte sehr ausführlich. Gehe auf jeden Aspekt einzeln ein.",
    }
    _ton_map = {
        "Förmlich":              "Der Ton soll durchgehend förmlich und professionell sein.",
        "Neutral":               "Der Ton soll neutral und sachlich sein.",
        "Informell":             "Der Ton darf informell und persönlich sein.",
        "Empathisch-förmlich":  "Der Ton soll förmlich, aber besonders empathisch und verständnisvoll sein.",
    }
    laenge_hint  = _laenge_map.get(laenge, "")
    ton_hint     = _ton_map.get(ton, "")
    extra_hint   = f"\nZusätzliche Vorgaben des Bearbeiters:\n{freitext_ctx}" if freitext_ctx else ""

    prompt = (
        "Du bist ein professioneller Beschwerdemanager beim Deutschen Roten Kreuz (DRK) "
        "am Flughafen Köln/Bonn.\n\n"
        f"{laenge_hint} {ton_hint}{extra_hint}\n\n"
        "Schreibe eine vollständige, professionelle Antwort-E-Mail an den Beschwerdeführer. "
        "Beginne direkt mit der Anrede (z.\u202fB. ‘Sehr geehrte/r …’). "
        "Kein Betreff, keine Zusammenfassung — nur der fertige Brief-/E-Mail-Text.\n\n"
        "Hinweis: Persönliche Daten wurden anonymisiert (z.\u202fB. [PERSON_1], [EMAIL_1], [TEL_1]). "
        "Belasse diese Platzhalter unverändert im Text — sie werden später lokal ersetzt.\n\n"
        f"Beschwerde:\n{anon_text}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
    }).encode("utf-8")

    wait_secs = [10, 30, 60]   # Wartezeiten bei 429
    last_err: Exception | None = None

    for attempt, wait in enumerate(wait_secs + [None], start=1):
        try:
            req = urllib.request.Request(
                _GEMINI_URL, data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                result = json.loads(r.read().decode("utf-8"))
            candidate = result["candidates"][0]
            text = candidate["content"]["parts"][0]["text"]
            finish = candidate.get("finishReason", "")
            if finish == "MAX_TOKENS":
                text += (
                    "\n\n⚠️  [Antwort wurde vom Modell wegen Token-Limit abgeschnitten. "
                    "Der Text oben ist möglicherweise unvollständig.]"
                )
            return text
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and wait is not None:
                import time
                time.sleep(wait)
                continue
            elif e.code == 429:
                raise RuntimeError(
                    "Gemini-API meldet 'Too Many Requests' (429).\n\n"
                    "Das kostenlose Kontingent ist vorübergehend erschöpft.\n"
                    "Bitte 1–2 Minuten warten und erneut versuchen.\n\n"
                    "Alternativ: Google Cloud Console → API-Quoten prüfen."
                ) from e
            raise
    raise last_err


# ══════════════════════════════════════════════════════════════════════════════
#  GUI-Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

def _btn(text: str, color: str = FIORI_BLUE, hover: str = "#0057b8") -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {color}; color: white; border: none;
            border-radius: 4px; padding: 4px 16px; font-size: 12px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ background: #bbb; color: #888; }}
    """)
    return b


def _badge_item(text: str, bg: str, fg: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setBackground(QColor(bg))
    item.setForeground(QColor(fg))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _ro_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


_FIELD_STYLE = (
    "QLineEdit, QTextEdit, QComboBox, QDateEdit {"
    "border:1px solid #ccc; border-radius:4px; padding:4px;"
    "font-size:12px; background:white;}"
)

# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Text-Vollansicht (wiederverwendbar)
# ══════════════════════════════════════════════════════════════════════════════

class _TextViewDialog(QDialog):
    """Zeigt einen beliebigen Text vollständig und scrollbar in einem eigenen Fenster."""

    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(720, 500)
        self.resize(860, 640)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(text)
        txt.setStyleSheet(
            "font-size:13px; font-family:'Segoe UI',sans-serif;"
            " background:white; padding:8px;"
        )
        root.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_copy = _btn("📋  In Zwischenablage kopieren", "#555", "#333")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        btn_close = _btn("Schließen", "#6c757d", "#5a6268")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)


# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Import (Freitext / Word / PDF)
# ══════════════════════════════════════════════════════════════════════════════

class _ImportDialog(QDialog):
    """Import einer Beschwerde aus Freitext, Word- oder PDF-Datei."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neue Beschwerde importieren")
        self.setMinimumSize(760, 680)
        self.setStyleSheet(_FIELD_STYLE)
        self._quelldatei = ""
        self._quelle = "Freitext"
        self._build()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # === Tabs: Freitext | Word | PDF ===
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #f8f9fa; }
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 12px;
                font-family: 'Segoe UI';
                color: #666;
                background: #e8ecf0;
                border-bottom: 2px solid transparent;
                border-radius: 4px 4px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #f8f9fa;
                color: #1565a8;
                font-weight: bold;
                border-bottom: 2px solid #1565a8;
            }
            QTabBar::tab:hover:!selected {
                background: #dde4ec;
                color: #1565a8;
            }
        """)
        self._tabs.currentChanged.connect(self._on_tab_change)

        # ── Tab 0: Freitext ──
        freitext_w = QWidget()
        flay = QVBoxLayout(freitext_w)
        flay.addWidget(QLabel("Beschwerdetext einfügen oder eingeben:"))
        self._freitext_edit = QTextEdit()
        self._freitext_edit.setPlaceholderText("Beschwerde hier einfügen …")
        flay.addWidget(self._freitext_edit)
        self._tabs.addTab(freitext_w, "✏️  Freitext")

        # ── Tab 1: Word ──
        word_w = QWidget()
        wlay = QVBoxLayout(word_w)
        path_row = QHBoxLayout()
        self._word_path = QLineEdit()
        self._word_path.setReadOnly(True)
        self._word_path.setPlaceholderText("Word-Datei (.docx) auswählen …")
        btn_word = _btn("📂  Durchsuchen", "#555", "#333")
        btn_word.clicked.connect(self._browse_word)
        path_row.addWidget(self._word_path)
        path_row.addWidget(btn_word)
        wlay.addLayout(path_row)
        wlay.addWidget(QLabel("Vorschau (extrahierter Text):"))
        self._word_preview = QTextEdit()
        self._word_preview.setReadOnly(True)
        self._word_preview.setStyleSheet("background:#f9f9f9; font-size:11px;")
        wlay.addWidget(self._word_preview)
        self._tabs.addTab(word_w, "📄  Word-Datei")

        # ── Tab 2: PDF ──
        pdf_w = QWidget()
        play = QVBoxLayout(pdf_w)
        pdf_row = QHBoxLayout()
        self._pdf_path = QLineEdit()
        self._pdf_path.setReadOnly(True)
        self._pdf_path.setPlaceholderText("PDF-Datei auswählen …")
        btn_pdf = _btn("📂  Durchsuchen", "#555", "#333")
        btn_pdf.clicked.connect(self._browse_pdf)
        pdf_row.addWidget(self._pdf_path)
        pdf_row.addWidget(btn_pdf)
        play.addLayout(pdf_row)
        play.addWidget(QLabel("Vorschau (extrahierter Text):"))
        self._pdf_preview = QTextEdit()
        self._pdf_preview.setReadOnly(True)
        self._pdf_preview.setStyleSheet("background:#f9f9f9; font-size:11px;")
        play.addWidget(self._pdf_preview)
        self._tabs.addTab(pdf_w, "📑  PDF-Datei")

        root.addWidget(self._tabs)

        # === Extrahieren-Button ===
        extr_row = QHBoxLayout()
        self._btn_extrahieren = _btn("🔍  Name & E-Mail automatisch extrahieren", "#6c757d", "#5a6268")
        self._btn_extrahieren.clicked.connect(self._extrahieren)
        extr_row.addWidget(self._btn_extrahieren)
        extr_row.addStretch()
        root.addLayout(extr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ddd;"); root.addWidget(sep)

        # === Metadaten-Formular ===
        form = QFormLayout()
        form.setSpacing(7)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._datum = QDateEdit()
        self._datum.setCalendarPopup(True)
        self._datum.setDate(QDate.currentDate())
        self._datum.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Datum Eingang:", self._datum)

        self._betroffener = QLineEdit()
        self._betroffener.setPlaceholderText("Betroffener Bereich / Abteilung")
        form.addRow("Betrifft:", self._betroffener)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Name des Beschwerdeführers")
        form.addRow("Name Beschwerdeführer:", self._name)

        self._email = QLineEdit()
        self._email.setPlaceholderText("E-Mail-Adresse")
        form.addRow("E-Mail:", self._email)

        self._kategorie = QComboBox()
        self._kategorie.addItems(KATEGORIEN)
        form.addRow("Kategorie:", self._kategorie)

        self._prioritaet = QComboBox()
        self._prioritaet.addItems(PRIORITAETEN)
        self._prioritaet.setCurrentText("Mittel")
        form.addRow("Priorität:", self._prioritaet)

        self._status = QComboBox()
        self._status.addItems(STATUS_OPTIONEN)
        form.addRow("Status:", self._status)

        self._massnahme = QTextEdit()
        self._massnahme.setFixedHeight(60)
        self._massnahme.setPlaceholderText("Eingeleitete oder geplante Maßnahme …")
        form.addRow("Maßnahme:", self._massnahme)

        root.addLayout(form)

        # === Buttons ===
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.button(QDialogButtonBox.StandardButton.Ok).setText("💾  Speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        box.accepted.connect(self._validate)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    # ── Slots ───────────────────────────────────────────────────────────────

    def _on_tab_change(self, idx: int):
        self._quelle = ["Freitext", "Word-Datei", "PDF-Datei"][idx]

    def _browse_word(self):
        pfad, _ = QFileDialog.getOpenFileName(
            self, "Word-Datei öffnen", "", "Word-Dokumente (*.docx)"
        )
        if pfad:
            self._word_path.setText(pfad)
            self._quelldatei = pfad
            text = _extrahiere_aus_word(pfad)
            self._word_preview.setPlainText(text)

    def _browse_pdf(self):
        pfad, _ = QFileDialog.getOpenFileName(
            self, "PDF-Datei öffnen", "", "PDF-Dateien (*.pdf)"
        )
        if pfad:
            self._pdf_path.setText(pfad)
            self._quelldatei = pfad
            text = _extrahiere_aus_pdf(pfad)
            self._pdf_preview.setPlainText(text)

    def _get_current_text(self) -> str:
        idx = self._tabs.currentIndex()
        if idx == 0:
            return self._freitext_edit.toPlainText()
        elif idx == 1:
            return self._word_preview.toPlainText()
        else:
            return self._pdf_preview.toPlainText()

    def _extrahieren(self):
        text = self._get_current_text()
        emails = _extrahiere_emails(text)
        namen = _extrahiere_namen(text)
        if emails:
            self._email.setText(emails[0])
        if namen:
            self._name.setText(namen[0])
        gefunden = []
        if emails:
            gefunden.append(f"E-Mails: {', '.join(emails)}")
        if namen:
            gefunden.append(f"Namen: {', '.join(namen)}")
        if gefunden:
            QMessageBox.information(
                self, "Extraktion",
                "Folgendes wurde gefunden:\n" + "\n".join(gefunden)
                + "\n\nBitte prüfen und ggf. korrigieren.",
            )
        else:
            QMessageBox.information(
                self, "Extraktion",
                "Keine E-Mail-Adressen oder Namen erkannt.\nBitte manuell eingeben.",
            )

    def _validate(self):
        text = self._get_current_text().strip()
        if not text:
            QMessageBox.warning(self, "Pflichtfeld", "Bitte Beschwerdetext eingeben oder Datei laden.")
            return
        self.accept()

    # ── Ergebnisabruf ──────────────────────────────────────────────────────

    def get_daten(self) -> dict:
        idx = self._tabs.currentIndex()
        quelldatei = ""
        if idx == 1:
            quelldatei = self._word_path.text()
        elif idx == 2:
            quelldatei = self._pdf_path.text()
        return {
            "datum_eingang":           self._datum.date().toString("dd.MM.yyyy"),
            "quelle":                  self._quelle,
            "quelldatei":              quelldatei,
            "originaltext":            self._get_current_text().strip(),
            "betroffener":             self._betroffener.text().strip(),
            "name_beschwerdefuehrer":   self._name.text().strip(),
            "email_beschwerdefuehrer":  self._email.text().strip(),
            "kategorie":               self._kategorie.currentText(),
            "prioritaet":              self._prioritaet.currentText(),
            "status":                  self._status.currentText(),
            "massnahme":               self._massnahme.toPlainText().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Bearbeiten
# ══════════════════════════════════════════════════════════════════════════════

class _BeschwerdeEditDialog(QDialog):
    """Bearbeiten einer bestehenden Beschwerde."""

    def __init__(self, daten: dict, parent=None):
        super().__init__(parent)
        self._daten = daten
        self.setWindowTitle(f"Beschwerde #{daten['id']} bearbeiten")
        self.setMinimumSize(680, 600)
        self.setStyleSheet(_FIELD_STYLE)
        self._build()
        self._prefill()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(7)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._datum = QDateEdit()
        self._datum.setCalendarPopup(True)
        self._datum.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Datum Eingang:", self._datum)

        self._quelle = QComboBox()
        self._quelle.addItems(QUELLEN)
        form.addRow("Quelle:", self._quelle)

        self._betroffener = QLineEdit()
        form.addRow("Betrifft:", self._betroffener)

        self._name = QLineEdit()
        form.addRow("Name Beschwerdeführer:", self._name)

        self._email = QLineEdit()
        form.addRow("E-Mail:", self._email)

        self._kategorie = QComboBox()
        self._kategorie.addItems(KATEGORIEN)
        form.addRow("Kategorie:", self._kategorie)

        self._prioritaet = QComboBox()
        self._prioritaet.addItems(PRIORITAETEN)
        form.addRow("Priorität:", self._prioritaet)

        self._status = QComboBox()
        self._status.addItems(STATUS_OPTIONEN)
        form.addRow("Status:", self._status)

        self._originaltext = QTextEdit()
        self._originaltext.setFixedHeight(80)
        form.addRow("Originaltext:", self._originaltext)

        self._massnahme = QTextEdit()
        self._massnahme.setFixedHeight(70)
        form.addRow("Maßnahme:", self._massnahme)

        self._gemini_antwort = QTextEdit()
        self._gemini_antwort.setFixedHeight(70)
        form.addRow("Gemini-Antwort:", self._gemini_antwort)

        root.addLayout(form)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.button(QDialogButtonBox.StandardButton.Ok).setText("💾  Speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def _prefill(self):
        d = self._daten
        try:
            tag, mon, jahr = d.get("datum_eingang", "").split(".")
            self._datum.setDate(QDate(int(jahr), int(mon), int(tag)))
        except Exception:
            self._datum.setDate(QDate.currentDate())
        self._quelle.setCurrentText(d.get("quelle", "Freitext"))
        self._betroffener.setText(d.get("betroffener", ""))
        self._name.setText(d.get("name_beschwerdefuehrer", ""))
        self._email.setText(d.get("email_beschwerdefuehrer", ""))
        self._kategorie.setCurrentText(d.get("kategorie", KATEGORIEN[0]))
        self._prioritaet.setCurrentText(d.get("prioritaet", "Mittel"))
        self._status.setCurrentText(d.get("status", "Offen"))
        self._originaltext.setPlainText(d.get("originaltext", ""))
        self._massnahme.setPlainText(d.get("massnahme", ""))
        self._gemini_antwort.setPlainText(d.get("gemini_antwort", ""))

    def get_daten(self) -> dict:
        return {
            **self._daten,
            "datum_eingang":           self._datum.date().toString("dd.MM.yyyy"),
            "quelle":                  self._quelle.currentText(),
            "betroffener":             self._betroffener.text().strip(),
            "name_beschwerdefuehrer":   self._name.text().strip(),
            "email_beschwerdefuehrer":  self._email.text().strip(),
            "kategorie":               self._kategorie.currentText(),
            "prioritaet":              self._prioritaet.currentText(),
            "status":                  self._status.currentText(),
            "originaltext":            self._originaltext.toPlainText().strip(),
            "massnahme":               self._massnahme.toPlainText().strip(),
            "gemini_antwort":          self._gemini_antwort.toPlainText().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Antwort per E-Mail
# ══════════════════════════════════════════════════════════════════════════════

class _AntwortDialog(QDialog):
    """Erstellt eine Antwort-E-Mail auf eine Beschwerde (über Outlook)."""

    def __init__(self, beschwerde: dict, parent=None):
        super().__init__(parent)
        self._beschwerde = beschwerde
        bid = beschwerde["id"]
        self.setWindowTitle(f"Antwort auf Beschwerde #{bid}")
        self.setMinimumSize(960, 780)
        self.resize(980, 820)
        self.setStyleSheet(_FIELD_STYLE)
        self._build()
        self._load_history()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(14, 12, 14, 12)

        # Info-Header
        info = QLabel(
            f"<b>Beschwerde #{self._beschwerde['id']}</b> &nbsp;|&nbsp; "
            f"{self._beschwerde.get('datum_eingang','')} &nbsp;|&nbsp; "
            f"{self._beschwerde.get('name_beschwerdefuehrer','—')} &nbsp;|&nbsp; "
            f"{self._beschwerde.get('status','')}"
        )
        info.setStyleSheet("background:#f0f4f8; padding:8px; border-radius:4px; font-size:12px;")
        root.addWidget(info)

        # ── Haupt-Splitter (vertikal) ────────────────────────────────────────
        main_split = QSplitter(Qt.Orientation.Vertical)

        # ── Oberes Panel: Original | Gemini ─────────────────────────────
        top_w = QWidget()
        top_lay = QHBoxLayout(top_w)
        top_lay.setSpacing(8)
        top_lay.setContentsMargins(0, 0, 0, 0)

        # Originaltext
        orig_grp = QGroupBox("📄  Originaltext")
        og_lay = QVBoxLayout(orig_grp)
        _orig_txt = self._beschwerde.get("originaltext", "")
        orig_hdr = QHBoxLayout()
        orig_hdr.addStretch()
        btn_orig_full = _btn("📋  Vollansicht", "#555", "#333")
        btn_orig_full.setFixedWidth(115)
        btn_orig_full.clicked.connect(
            lambda: _TextViewDialog("Originaltext der Beschwerde", _orig_txt, self).exec()
        )
        orig_hdr.addWidget(btn_orig_full)
        og_lay.addLayout(orig_hdr)
        orig_prev = QTextEdit()
        orig_prev.setReadOnly(True)
        orig_prev.setPlainText(_orig_txt)
        orig_prev.setStyleSheet("background:#fafafa; font-size:11px;")
        og_lay.addWidget(orig_prev)
        top_lay.addWidget(orig_grp, 1)

        # Gemini-Antwort
        gem_grp = QGroupBox("🤖  Gemini-Antwort (Entwurf)")
        gem_grp.setStyleSheet(
            "QGroupBox { border:1px solid #c8aff0; border-radius:6px; margin-top:6px; }"
            "QGroupBox::title { color:#6f42c1; font-weight:bold;"
            " subcontrol-origin:margin; padding:2px 8px; }"
        )
        gem_lay = QVBoxLayout(gem_grp)
        _gem_txt = self._beschwerde.get("gemini_antwort", "") or ""
        gem_hdr = QHBoxLayout()
        gem_hdr.addStretch()
        btn_gem_full = _btn("📋  Vollansicht", "#6f42c1", "#5e35b1")
        btn_gem_full.setFixedWidth(115)
        btn_gem_full.clicked.connect(
            lambda: _TextViewDialog("🤖 Gemini-Antwort", _gem_txt, self).exec()
        )
        gem_hdr.addWidget(btn_gem_full)
        gem_lay.addLayout(gem_hdr)
        self._gemini_preview = QTextEdit()
        self._gemini_preview.setReadOnly(True)
        self._gemini_preview.setPlainText(
            _gem_txt if _gem_txt
            else "(Noch keine Gemini-Antwort — bitte zuerst Gemini-Analyse durchführen und speichern)"
        )
        self._gemini_preview.setStyleSheet("background:#f9f4ff; font-size:11px;")
        gem_lay.addWidget(self._gemini_preview)

        # De-Anonymisierungs-Option
        deanon_frame = QFrame()
        deanon_frame.setStyleSheet(
            "QFrame { background:#fff8e7; border:1px solid #ffd166; border-radius:4px; }"
        )
        deanon_lay_v = QVBoxLayout(deanon_frame)
        deanon_lay_v.setContentsMargins(8, 5, 8, 5)
        deanon_lay_v.setSpacing(2)
        self._cb_deanon = QCheckBox(
            "Persönliche Daten lokal wiederherstellen  ([PERSON_1] → echter Name, etc.)"
        )
        self._cb_deanon.setChecked(True)
        self._cb_deanon.setStyleSheet("font-size:11px; font-weight:bold;")
        deanon_lay_v.addWidget(self._cb_deanon)
        deanon_note = QLabel(
            "⚠️  Persönliche Daten befinden sich <b>nur lokal</b> auf diesem Gerät. "
            "Sie wurden <b>NICHT</b> an Gemini übermittelt."
        )
        deanon_note.setStyleSheet("font-size:10px; color:#856404;")
        deanon_note.setWordWrap(True)
        deanon_lay_v.addWidget(deanon_note)
        gem_lay.addWidget(deanon_frame)

        btn_uebernehmen = _btn("⬇  Als Antworttext übernehmen", "#6f42c1", "#5e35b1")
        btn_uebernehmen.clicked.connect(self._uebernehme_gemini)
        gem_lay.addWidget(btn_uebernehmen)
        top_lay.addWidget(gem_grp, 1)
        main_split.addWidget(top_w)

        # ── Unteres Panel: Formular + History ───────────────────────────
        bot_w = QWidget()
        bot_lay = QVBoxLayout(bot_w)
        bot_lay.setContentsMargins(0, 4, 0, 0)
        bot_lay.setSpacing(6)

        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._an = QLineEdit()
        self._an.setText(self._beschwerde.get("email_beschwerdefuehrer", ""))
        self._an.setPlaceholderText("E-Mail-Adresse des Empfängers")
        form.addRow("An:", self._an)
        self._betreff = QLineEdit()
        self._betreff.setText(
            f"Antwort auf Ihre Beschwerde vom {self._beschwerde.get('datum_eingang','')}"
        )
        form.addRow("Betreff:", self._betreff)
        bot_lay.addLayout(form)

        antw_hdr = QHBoxLayout()
        antw_hdr.addWidget(QLabel("<b>Antworttext:</b>"))
        antw_hdr.addStretch()
        btn_antw_full = _btn("📋  Vollansicht", "#555", "#333")
        btn_antw_full.setFixedWidth(115)
        btn_antw_full.clicked.connect(
            lambda: _TextViewDialog(
                "Antworttext", self._antworttext.toPlainText(), self
            ).exec()
        )
        antw_hdr.addWidget(btn_antw_full)
        bot_lay.addLayout(antw_hdr)
        self._antworttext = QTextEdit()
        self._antworttext.setPlaceholderText("Antworttext eingeben …")
        self._antworttext.setMinimumHeight(100)
        bot_lay.addWidget(self._antworttext, 1)

        # Bisherige Antworten
        self._history_group = QGroupBox("Bisherige Antworten")
        hist_grp_lay = QVBoxLayout(self._history_group)
        hist_grp_lay.setContentsMargins(6, 4, 6, 4)
        self._hist_container = QWidget()
        self._hist_lay = QVBoxLayout(self._hist_container)
        self._hist_lay.setContentsMargins(0, 0, 0, 0)
        self._hist_lay.setSpacing(4)
        hist_scroll = QScrollArea()
        hist_scroll.setWidgetResizable(True)
        hist_scroll.setWidget(self._hist_container)
        hist_scroll.setFixedHeight(90)
        hist_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        hist_grp_lay.addWidget(hist_scroll)
        bot_lay.addWidget(self._history_group)

        main_split.addWidget(bot_w)
        main_split.setSizes([300, 420])
        root.addWidget(main_split, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_outlook = _btn("📧  In Outlook öffnen", "#0a6ed1")
        btn_outlook.clicked.connect(self._outlook_oeffnen)
        btn_row.addWidget(btn_outlook)
        btn_row.addStretch()
        root.addLayout(btn_row)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.button(QDialogButtonBox.StandardButton.Ok).setText("💾  Antwort speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Schließen")
        box.accepted.connect(self._speichern)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def _load_history(self):
        antworten = lade_antworten(self._beschwerde["id"])
        while self._hist_lay.count():
            item = self._hist_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not antworten:
            lbl = QLabel("  (Noch keine Antworten vorhanden)")
            lbl.setStyleSheet("color:#888; font-size:11px; padding:4px;")
            self._hist_lay.addWidget(lbl)
        else:
            for a in antworten:
                card = QFrame()
                card.setStyleSheet(
                    "QFrame { background:#f0f8ff; border:1px solid #bee3f8;"
                    " border-radius:5px; }"
                )
                c_lay = QHBoxLayout(card)
                c_lay.setContentsMargins(8, 5, 8, 5)
                info_lay = QVBoxLayout()
                info_lay.setSpacing(1)
                top_lbl = QLabel(
                    f"<b>{a.get('datum','—')}</b>  →  {a.get('empfaenger','')}"
                )
                top_lbl.setStyleSheet("font-size:11px; color:#333;")
                info_lay.addWidget(top_lbl)
                raw = a.get("antworttext", "") or ""
                prev = raw.replace("\n", " ")[:100]
                if len(raw) > 100:
                    prev += "…"
                prev_lbl = QLabel(prev)
                prev_lbl.setStyleSheet("font-size:11px; color:#666;")
                prev_lbl.setWordWrap(True)
                info_lay.addWidget(prev_lbl)
                c_lay.addLayout(info_lay, 1)
                btn_lesen = _btn("📖  Lesen", "#17a2b8", "#138496")
                btn_lesen.setFixedWidth(90)
                _t, _d = raw, a.get("datum", "")
                btn_lesen.clicked.connect(
                    lambda _, t=_t, dat=_d: _TextViewDialog(
                        f"Antwort vom {dat}", t, self
                    ).exec()
                )
                c_lay.addWidget(btn_lesen)
                self._hist_lay.addWidget(card)
        self._hist_lay.addStretch()

    def _uebernehme_gemini(self):
        """Gemini-Antwort als Antworttext übernehmen, optional mit De-Anonymisierung."""
        gemini_text = (self._beschwerde.get("gemini_antwort", "") or "").strip()
        if not gemini_text:
            QMessageBox.information(
                self, "Keine Gemini-Antwort",
                "Für diese Beschwerde liegt noch keine gespeicherte Gemini-Antwort vor.\n"
                "Bitte zuerst über ‘🤖 Gemini-Analyse’ eine Antwort erstellen und speichern."
            )
            return
        text = self._deanonymisiere_lokal(gemini_text) if self._cb_deanon.isChecked() else gemini_text
        self._antworttext.setPlainText(text)

    def _deanonymisiere_lokal(self, text: str) -> str:
        """Setzt bekannte Anonymisierungs-Platzhalter lokal zurück."""
        result = text
        name  = self._beschwerde.get("name_beschwerdefuehrer",  "").strip()
        email = self._beschwerde.get("email_beschwerdefuehrer", "").strip()
        b = self._beschwerde
        if name:
            result = result.replace("[PERSON_1]", name)
        if email:
            result = result.replace("[EMAIL_1]", email)
        # Anrede: Sehr geehrte/r [PERSON_1] → korrektes Geschlecht wenn möglich
        return result

    def _outlook_oeffnen(self):
        an = self._an.text().strip()
        betreff = self._betreff.text().strip()
        text = self._antworttext.toPlainText().strip()
        if not an:
            QMessageBox.warning(self, "Pflichtfeld", "Bitte E-Mail-Adresse des Empfängers angeben.")
            return
        try:
            from functions.mail_functions import create_outlook_draft
            create_outlook_draft(to=an, subject=betreff, body_text=text)
        except Exception as e:
            QMessageBox.critical(self, "Outlook-Fehler", str(e))

    def _speichern(self):
        an = self._an.text().strip()
        betreff = self._betreff.text().strip()
        text = self._antworttext.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Pflichtfeld", "Bitte Antworttext eingeben.")
            return
        try:
            antwort_speichern({
                "beschwerde_id": self._beschwerde["id"],
                "empfaenger":    an,
                "betreff":       betreff,
                "antworttext":   text,
            })
            QMessageBox.information(self, "Gespeichert", "Antwort wurde gespeichert.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Gemini Reasoning – interaktiver Chat
# ══════════════════════════════════════════════════════════════════════════════

class _GeminiReasoningDialog(QDialog):
    """
    Interaktiver Gemini-Chat: Beschwerde analysieren & Antwort wie mit
    einem Kollegen gemeinsam formulieren.

    Ablauf:
    1. Gemini analysiert die anonymisierte Beschwerde und stellt Fragen.
    2. Der Nutzer antwortet – Gemini schreibt einen Entwurf.
    3. Der Nutzer gibt Feedback – Gemini passt an (beliebig oft).
    4. Zufrieden? → Gemini sendet [FINALER_BRIEF] + fertigen Brief.
    5. Brief kann direkt gespeichert werden.
    """

    _SYS = (
        "Du bist ein erfahrener Beschwerdemanager beim DRK (Deutsches Rotes Kreuz) "
        "am Flughafen Köln/Bonn. Du hilfst dem Nutzer Schritt für Schritt, eine "
        "professionelle Antwort auf eine Patientenbeschwerde zu formulieren.\n\n"
        "**Wichtige Regeln – unbedingt einhalten:**\n"
        "1. Stelle immer nur EINE kurze, klare Frage auf einmal (maximal 2 Sätze). "
        "Keine Liste von Fragen.\n"
        "2. Ab der zweiten Nachricht: Zeige IMMER zuerst den aktuellen vollständigen "
        "Briefentwurf. Markiere Änderungen gegenüber dem letzten Entwurf mit >>> ... <<< "
        "(z. B. >>>neu hinzugefügter Satz<<<).\n"
        "3. Stelle dann UNTER dem Brief eine weitere kurze Frage oder bitte um Freigabe.\n"
        "4. Starte nach der Beschwerde-Analyse sofort mit dem ersten Briefentwurf, dann "
        "erst die erste Frage.\n"
        "5. Wenn der Nutzer zufrieden ist, antworte MIT DIESEM EXAKTEN FORMAT – ohne "
        "weitere Kommentare danach:\n"
        "   [FINALER_BRIEF]\n"
        "   <vollständiger Brieftext>\n\n"
        "Hinweis: Persönliche Daten wurden anonymisiert (z. B. [PERSON_1], [EMAIL_1], "
        "[TEL_1]). Belasse diese Platzhalter UNVERÄNDERT.\n\n"
        "Antworte immer auf Deutsch."
    )

    def __init__(self, beschwerde: dict, parent=None):
        super().__init__(parent)
        self._beschwerde = beschwerde
        self._conversation: list[dict] = []
        self._signals = _GeminiConvSignals()
        self._signals.fertig.connect(self._on_response)
        self._signals.fehler.connect(self._on_error)

        # Auto-Anonymisierung
        orig = beschwerde.get("originaltext", "").strip()
        emails = [e for e in [beschwerde.get("email_beschwerdefuehrer", "").strip()] if e]
        namen  = [n for n in [beschwerde.get("name_beschwerdefuehrer",  "").strip()] if n]
        telefone = _extrahiere_telefon(orig)
        self._anon_text, self._anon_mapping = _anonymisiere_text(
            orig, emails, namen, telefone
        )

        self.setWindowTitle(f"🧠  Gemini Reasoning — Beschwerde #{beschwerde['id']}")
        self.setMinimumSize(1020, 720)
        self.resize(1080, 780)
        self.setStyleSheet(_FIELD_STYLE)
        self._build()
        QTimer.singleShot(400, self._start_conversation)

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 10, 12, 10)

        # Hinweis-Banner
        banner = QLabel(
            "🤝  <b>Gemini Reasoning</b> — Arbeiten Sie mit Gemini wie mit einem Kollegen. "
            "Gemini analysiert die Beschwerde und stellt Ihnen Fragen zur Antwortgestaltung.  "
            "<span style='color:#856404;'>⚠️  Nur der anonymisierte Text wird übermittelt — "
            "persönliche Daten bleiben ausschließlich lokal.</span>"
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background:#fff3cd; padding:8px; border-radius:4px; font-size:11px;"
        )
        root.addWidget(banner)

        # Haupt-Splitter: Links Chat | Rechts Anontext + Briefergebnis
        split = QSplitter(Qt.Orientation.Horizontal)

        # ── Linke Seite: Chat ──────────────────────────────────────────────
        chat_w = QWidget()
        cl = QVBoxLayout(chat_w)
        cl.setContentsMargins(0, 0, 4, 0)
        cl.setSpacing(6)
        cl.addWidget(QLabel("<b>💬  Gespräch mit Gemini:</b>"))

        self._chat_container = QWidget()
        self._chat_vlay = QVBoxLayout(self._chat_container)
        self._chat_vlay.setContentsMargins(4, 4, 4, 4)
        self._chat_vlay.setSpacing(6)
        self._chat_vlay.addStretch()

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setWidget(self._chat_container)
        self._chat_scroll.setStyleSheet(
            "QScrollArea { border:1px solid #ddd; border-radius:4px; background:#fff; }"
        )
        cl.addWidget(self._chat_scroll, 1)

        # Schnell-Auswahl Chips
        chips_hdr = QLabel("<b>Schnellauswahl:</b>")
        chips_hdr.setStyleSheet("font-size:11px; color:#555;")
        cl.addWidget(chips_hdr)
        self._chips_scroll = QScrollArea()
        self._chips_scroll.setWidgetResizable(True)
        self._chips_scroll.setFixedHeight(68)
        self._chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chips_scroll.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
        )
        self._chips_w = QWidget()
        self._chips_lay = QHBoxLayout(self._chips_w)
        self._chips_lay.setContentsMargins(0, 2, 0, 2)
        self._chips_lay.setSpacing(5)
        self._chips_lay.addStretch()
        self._chips_scroll.setWidget(self._chips_w)
        cl.addWidget(self._chips_scroll)

        # Eingabe
        inp_lay = QHBoxLayout()
        self._user_input = QTextEdit()
        self._user_input.setPlaceholderText(
            "Ihre Antwort an Gemini … (z.\u202fB. 'Förmlich, kurz, Kulanz anbieten')  "
            "  Strg+Enter zum Senden"
        )
        self._user_input.setFixedHeight(72)
        self._user_input.installEventFilter(self)
        self._btn_send = _btn("📤  Senden", "#0a6ed1", "#085099")
        self._btn_send.setFixedWidth(110)
        self._btn_send.setEnabled(False)
        self._btn_send.clicked.connect(self._send_user_message)
        inp_lay.addWidget(self._user_input, 1)
        inp_lay.addWidget(self._btn_send)
        cl.addLayout(inp_lay)

        self._status_lbl = QLabel("⏳  Gemini wird gestartet …")
        self._status_lbl.setStyleSheet("color:#666; font-size:11px;")
        cl.addWidget(self._status_lbl)
        split.addWidget(chat_w)

        # ── Rechte Seite: Anonymisierter Text + fertiger Brief ─────────────
        right_w = QWidget()
        rl = QVBoxLayout(right_w)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(6)

        anon_grp = QGroupBox("📄  Anonymisierter Text (wird an Gemini gesendet)")
        ag = QVBoxLayout(anon_grp)
        # Zeige Anzahl der Ersetzungen
        n_rep = len(self._anon_mapping)
        if n_rep:
            rep_lbl = QLabel(f"✅  {n_rep} Ersetzung(en) — Original-Daten bleiben lokal.")
            rep_lbl.setStyleSheet("font-size:10px; color:#155724; padding:2px 0;")
            ag.addWidget(rep_lbl)
        else:
            rep_lbl = QLabel("ℹ️  Keine markierten Daten erkannt — Text wie eingegeben.")
            rep_lbl.setStyleSheet("font-size:10px; color:#856404; padding:2px 0;")
            ag.addWidget(rep_lbl)
        self._anon_prev = QTextEdit()
        self._anon_prev.setReadOnly(True)
        self._anon_prev.setPlainText(self._anon_text)
        self._anon_prev.setStyleSheet("font-size:11px; background:#fafafa;")
        ag.addWidget(self._anon_prev)
        rl.addWidget(anon_grp, 1)

        res_grp = QGroupBox("✉️  Fertig formulierter Antwortbrief")
        res_grp.setStyleSheet(
            "QGroupBox { border:1px solid #c8aff0; border-radius:6px; margin-top:6px; }"
            "QGroupBox::title { color:#6f42c1; font-weight:bold; "
            "subcontrol-origin:margin; padding:2px 8px; }"
        )
        rg = QVBoxLayout(res_grp)
        self._result_edit = QTextEdit()
        self._result_edit.setPlaceholderText(
            "(Hier erscheint der fertige Antwortbrief, sobald Gemini ihn "
            "mit [FINALER_BRIEF] markiert hat. Sie können ihn danach noch bearbeiten.)"
        )
        self._result_edit.setStyleSheet("font-size:11px;")
        rg.addWidget(self._result_edit, 1)

        btn_r = QHBoxLayout()
        btn_r.addStretch()
        btn_fullview = _btn("📋  Vollansicht", "#555", "#333")
        btn_fullview.setFixedWidth(115)
        btn_fullview.clicked.connect(
            lambda: _TextViewDialog(
                "Fertig formulierter Antwortbrief",
                self._result_edit.toPlainText(), self
            ).exec()
        )
        btn_r.addWidget(btn_fullview)
        btn_speichern = _btn("💾  Als Gemini-Antwort speichern", "#6f42c1", "#5e35b1")
        btn_speichern.clicked.connect(self._speichern)
        btn_r.addWidget(btn_speichern)
        rg.addLayout(btn_r)
        rl.addWidget(res_grp, 1)
        split.addWidget(right_w)

        split.setSizes([530, 470])
        root.addWidget(split, 1)

        close_row = QHBoxLayout()
        self._btn_restart = _btn("🔄  Führung neu starten", "#17a2b8", "#138496")
        self._btn_restart.setToolTip(
            "Chat zurücksetzen und die geführten Fragen von vorne beginnen."
        )
        self._btn_restart.clicked.connect(self._restart_conversation)
        close_row.addWidget(self._btn_restart)
        close_row.addStretch()
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.reject)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

    # ── Event-Filter: Strg+Enter sendet ─────────────────────────────────────

    def eventFilter(self, obj, event):
        if (
            obj is self._user_input
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Return
            and (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            self._send_user_message()
            return True
        return super().eventFilter(obj, event)

    # ── Chat-Hilfsmethoden ───────────────────────────────────────────────────

    def _add_message(self, role: str, text: str):
        """Fügt eine Nachricht-Karte in den Chat-Verlauf ein."""
        is_gemini = role == "model"
        card = QFrame()
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(10, 8, 10, 8)
        c_lay.setSpacing(3)

        hdr = QLabel("🤖  Gemini" if is_gemini else "👤  Sie")
        hdr.setStyleSheet(
            f"font-weight:bold; font-size:11px; "
            f"color:{'#6f42c1' if is_gemini else '#0a6ed1'};"
        )
        c_lay.addWidget(hdr)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet("font-size:12px; color:#222;")
        c_lay.addWidget(body)

        bg     = "#f9f4ff" if is_gemini else "#e8f4fd"
        border = "#c8aff0" if is_gemini else "#bee3f8"
        card.setStyleSheet(
            f"QFrame {{ background:{bg}; border:1px solid {border}; border-radius:6px; }}"
        )
        # Einfügen vor dem abschließenden Stretch
        self._chat_vlay.insertWidget(self._chat_vlay.count() - 1, card)
        QTimer.singleShot(
            60,
            lambda: self._chat_scroll.verticalScrollBar().setValue(
                self._chat_scroll.verticalScrollBar().maximum()
            ),
        )

    # ── Konversations-Logik ──────────────────────────────────────────────────

    def _start_conversation(self):
        first_msg = (
            "Analysiere bitte die folgende Beschwerde, schreibe sofort einen ersten "
            "professionellen Briefentwurf und stelle danach NUR EINE kurze Frage "
            "zur Anpassung (Ton, Kulanz, Maßnahmen o.ä.):\n\n"
            + self._anon_text
        )
        self._conversation = [{"role": "user", "parts": [{"text": first_msg}]}]
        self._run_gemini()

    def _send_user_message(self):
        text = self._user_input.toPlainText().strip()
        if not text:
            return
        self._user_input.clear()
        self._btn_send.setEnabled(False)
        self._add_message("user", text)
        self._conversation.append({"role": "user", "parts": [{"text": text}]})
        self._run_gemini()

    def _run_gemini(self):
        self._status_lbl.setText("⏳  Gemini denkt nach …")
        sig  = self._signals
        conv = list(self._conversation)
        sys_p = self._SYS

        def worker():
            try:
                payload = {
                    "system_instruction": {"parts": [{"text": sys_p}]},
                    "contents": conv,
                    "generationConfig": {
                        "maxOutputTokens": 8192,
                        "temperature": 0.7,
                    },
                }
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    _GEMINI_URL,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    sig.fehler.emit("Keine Antwort von Gemini erhalten.")
                    return
                text = candidates[0]["content"]["parts"][0]["text"].strip()
                if candidates[0].get("finishReason") == "MAX_TOKENS":
                    text += (
                        "\n\n⚠️ [Antwort möglicherweise unvollständig – Token-Limit erreicht]"
                    )
                sig.fertig.emit(text)
            except Exception as exc:
                sig.fehler.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_response(self, text: str):
        self._conversation.append({"role": "model", "parts": [{"text": text}]})
        turn = len([m for m in self._conversation if m["role"] == "model"])
        if "[FINALER_BRIEF]" in text:
            pre, letter = text.split("[FINALER_BRIEF]", 1)
            letter = letter.strip()
            self._result_edit.setPlainText(letter)
            if pre.strip():
                self._add_message("model", pre.strip())
            self._add_message(
                "model",
                "✉️  Der fertige Antwortbrief wurde rechts angezeigt. "
                "Sie können ihn dort noch bearbeiten und dann unten rechts speichern.",
            )
            self._set_chips([
                ("✅  So passt es – speichern",   "[FINALER_BRIEF]"),
                ("✏️  Noch kürzer",              "Bitte mach den Brief noch kürzer."),
                ("✏️  Noch formaler",             "Bitte formuliere formaler."),
                ("✏️  Wärmere Worte",             "Bitte etwas wärmer und empathischer formulieren."),
            ], show_skip=False)
        else:
            self._add_message("model", text)
            # Kontextabhängige Chips je nach Turn
            if turn == 1:
                # Erster Entwurf – grundlegende Stilfragen
                self._set_chips([
                    ("Ton: Förmlich",                   "Bitte formaler und distanzierter formulieren."),
                    ("Ton: Empathisch",                 "Bitte empathischer und wärmer formulieren."),
                    ("Ton: Neutral",                    "Bitte neutral und sachlich formulieren."),
                    ("Länge: Kürzer",                   "Bitte den Brief deutlich kürzer fassen."),
                    ("Länge: Ausführlicher",            "Bitte den Brief ausführlicher gestalten."),
                ])
            elif turn == 2:
                # Nach erstem Feedback – Inhaltsfragen
                self._set_chips([
                    ("Entschuldigung hinzufügen",       "Bitte eine aufrichtige Entschuldigung einfügen."),
                    ("Kulanz anbieten",                 "Bitte ein konkretes Kulanzangebot einfügen."),
                    ("Mitarbeiter einbeziehen",          "Bitte erwähnen, dass der Vorfall intern besprochen wird."),
                    ("Mitarbeiter NICHT erwähnen",      "Bitte keine Mitarbeiter oder interne Abläufe erwähnen."),
                    ("Prüfung zusagen",                 "Bitte zusagen, dass der Vorfall intern geprüft wird."),
                ])
            elif turn == 3:
                # Dritter Turn – Namensfragen
                self._set_chips([
                    ("Namen der MA nennen",             "Bitte die Namen der beteiligten Mitarbeiter im Brief nennen (Platzhalter verwenden)."),
                    ("Namen der MA NICHT nennen",       "Bitte keine Namen von Mitarbeitern nennen."),
                    ("Rückruf anbieten",                "Bitte ein persönliches Rückrufangebot einfügen."),
                    ("Verbesserung kommunizieren",      "Bitte kommunizieren, dass Prozessverbesserungen eingeleitet werden."),
                    ("Nachschulung erwähnen",           "Bitte erwähnen, dass eine Nachschulung erfolgt."),
                ])
            else:
                # Spätere Turns – Feinschliff
                self._set_chips([
                    ("Abschluss wärmer",                "Bitte den Abschluss des Briefes wärmer gestalten."),
                    ("Abschluss formaler",               "Bitte den Abschluss formaler und professioneller gestalten."),
                    ("Betreff anpassen",                 "Bitte einen passenden Betreff für den Brief vorschlagen."),
                    ("Passt so – Entwurf finalisieren", "Ich bin zufrieden. Bitte den fertigen Brief mit [FINALER_BRIEF] ausgeben."),
                    ("Nochmal überarbeiten",             "Bitte den gesamten Brief nochmal überarbeiten und verbessern."),
                ])
        self._status_lbl.setText("✅  Antwort erhalten — Ihre Eingabe ist jetzt möglich.")
        self._btn_send.setEnabled(True)
        self._user_input.setFocus()

    def _set_chips(self, chips: list[tuple[str, str]], show_skip: bool = True):
        """Ersetzt alle Schnellauswahl-Buttons. chips = [(Label, Nachricht), ...]"""
        # Alle vorhandenen Chips entfernen (außer Stretch am Ende)
        while self._chips_lay.count() > 1:
            item = self._chips_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        _all = list(chips)
        if show_skip and _all:
            _all.append(("➡️  Nichts ändern / Weiter", "__skip__"))
        for label, msg in _all:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if msg == "[FINALER_BRIEF]":
                btn.setStyleSheet(
                    "QPushButton { background:#28a745; color:#fff; border-radius:14px;"
                    " padding:2px 12px; font-size:11px; font-weight:bold; }"
                    "QPushButton:hover { background:#218838; }"
                )
                btn.clicked.connect(
                    lambda: self._send_direct(
                        "Ich bin zufrieden. Bitte den fertigen Brief mit [FINALER_BRIEF] ausgeben."
                    )
                )
            elif msg == "__skip__":
                btn.setStyleSheet(
                    "QPushButton { background:#f8f9fa; color:#6c757d; border:1px solid #dee2e6;"
                    " border-radius:14px; padding:2px 12px; font-size:11px; }"
                    "QPushButton:hover { background:#e9ecef; color:#495057; }"
                )
                btn.clicked.connect(
                    lambda: self._send_direct(
                        "Dieser Aspekt passt so. Bitte stelle die nächste Frage zur Antwortgestaltung."
                    )
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background:#e8f0fe; color:#1a56db; border:1px solid #c7d7fc;"
                    " border-radius:14px; padding:2px 12px; font-size:11px; }"
                    "QPushButton:hover { background:#c7d7fc; }"
                )
                _m = msg
                btn.clicked.connect(lambda _, m=_m: self._send_direct(m))
            self._chips_lay.insertWidget(self._chips_lay.count() - 1, btn)

    def _send_direct(self, msg: str):
        """Chip-Klick: Nachricht direkt senden ohne Textfeld."""
        if not self._btn_send.isEnabled():
            return
        self._user_input.setPlainText(msg)
        self._send_user_message()

    def _restart_conversation(self):
        """Setzt Chat komplett zurück und startet geführte Eingabe neu."""
        # Alle Chat-Karten entfernen (außer abschließendem Stretch)
        while self._chat_vlay.count() > 1:
            item = self._chat_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Briefentwurf und Chips leeren
        self._result_edit.clear()
        self._set_chips([], show_skip=False)
        # Eingabe leeren, Konversation zurücksetzen
        self._user_input.clear()
        self._conversation = []
        self._btn_send.setEnabled(False)
        self._status_lbl.setText("⏳  Gemini wird neu gestartet …")
        QTimer.singleShot(300, self._start_conversation)

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"❌  Fehler: {msg[:80]}")
        self._btn_send.setEnabled(True)
        self._add_message("model", f"⚠️  Fehler bei Gemini-Anfrage: {msg}")

    def _speichern(self):
        text = self._result_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, "Kein Brief",
                "Bitte erst mit Gemini einen Antwortbrief formulieren.\n"
                "Wenn Gemini fertig ist, erscheint der Brief rechts.",
            )
            return
        daten = dict(self._beschwerde)
        daten["gemini_antwort"] = text
        try:
            beschwerde_aktualisieren(self._beschwerde["id"], daten)
            self._beschwerde["gemini_antwort"] = text
            QMessageBox.information(self, "Gespeichert", "Gemini-Antwort wurde gespeichert.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  Helper: Signals für Threaded Gemini-Anfragen
# ══════════════════════════════════════════════════════════════════════════════

class _GeminiConvSignals(QObject):
    """Signals für den Reasoning-Dialog (Multi-Turn)."""
    fertig = Signal(str)
    fehler = Signal(str)


class _GeminiSignals(QObject):
    fertig = Signal(str)
    fehler = Signal(str)


# ══════════════════════════════════════════════════════════════════════════════
#  Dialog: Gemini-Analyse mit Anonymisierung
# ══════════════════════════════════════════════════════════════════════════════

class _GeminiDialog(QDialog):
    """
    2-Schritt-Anonymisierung + Gemini-Analyse.
    Schritt 1: Anonymisierten Text zeigen → user bestätigt
    Schritt 2: Erst dann wird an Gemini gesendet
    """

    def __init__(self, beschwerde: dict, parent=None):
        super().__init__(parent)
        self._beschwerde = beschwerde
        self._anon_text = ""
        self._gemini_sig = _GeminiSignals()
        self._gemini_sig.fertig.connect(self._on_gemini_fertig)
        self._gemini_sig.fehler.connect(self._on_gemini_fehler)

        self.setWindowTitle(f"🤖  Gemini-Analyse — Beschwerde #{beschwerde['id']}")
        self.setMinimumSize(1100, 840)
        self.setStyleSheet(_FIELD_STYLE)
        self._build()
        self._init_anon_items()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ─── Hauptsplit: links=Original+Anon | rechts=Gemini-Antwort ───────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Linke Seite ──────────────────────────────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setSpacing(8)

        # Originaltext
        orig_grp = QGroupBox("📄  Originaltext (Beschwerde)")
        og_lay = QVBoxLayout(orig_grp)
        self._orig_edit = QTextEdit()
        self._orig_edit.setReadOnly(True)
        self._orig_edit.setFixedHeight(150)
        self._orig_edit.setPlainText(self._beschwerde.get("originaltext", ""))
        self._orig_edit.setStyleSheet("font-size:11px; background:#fafafa;")
        og_lay.addWidget(self._orig_edit)
        left_lay.addWidget(orig_grp)

        # Anonymisierung
        anon_grp = QGroupBox("🔒  Anonymisierung — was soll ersetzt werden?")
        anon_lay = QVBoxLayout(anon_grp)

        # E-Mails
        anon_lay.addWidget(QLabel("<b>E-Mail-Adressen:</b>"))
        self._email_checks: list[QCheckBox] = []
        self._email_check_widget = QWidget()
        self._email_check_lay = QVBoxLayout(self._email_check_widget)
        self._email_check_lay.setContentsMargins(0, 0, 0, 0)
        anon_lay.addWidget(self._email_check_widget)

        # Namen
        anon_lay.addWidget(QLabel("<b>Namen:</b>"))
        self._name_checks: list[QCheckBox] = []
        self._name_check_widget = QWidget()
        self._name_check_lay = QVBoxLayout(self._name_check_widget)
        self._name_check_lay.setContentsMargins(0, 0, 0, 0)
        anon_lay.addWidget(self._name_check_widget)

        # Telefonnummern
        anon_lay.addWidget(QLabel("<b>Telefonnummern:</b>"))
        self._tel_checks: list[QCheckBox] = []
        self._tel_check_widget = QWidget()
        self._tel_check_lay = QVBoxLayout(self._tel_check_widget)
        self._tel_check_lay.setContentsMargins(0, 0, 0, 0)
        anon_lay.addWidget(self._tel_check_widget)

        # Zusätzliche Begriffe
        anon_lay.addWidget(QLabel("<b>Zusätzliche Begriffe</b> (ein Begriff pro Zeile):"))
        self._extra_edit = QTextEdit()
        self._extra_edit.setFixedHeight(55)
        self._extra_edit.setPlaceholderText("z. B. Stationsnamen, Ortsnamen …")
        anon_lay.addWidget(self._extra_edit)

        # Vorschau-Button
        btn_preview = _btn("👁  Anonymisierten Text generieren & anzeigen", "#6c757d", "#5a6268")
        btn_preview.clicked.connect(self._generate_preview)
        anon_lay.addWidget(btn_preview)

        left_lay.addWidget(anon_grp)

        # Anonymisierter Text (MUSS gesehen werden vor dem Senden)
        prev_grp = QGroupBox("⚠️  Anonymisierter Text — wird so an Gemini gesendet")
        prev_grp.setStyleSheet(
            "QGroupBox { border:2px solid #e74c3c; border-radius:6px;"
            "margin-top:6px; font-weight:bold; color:#e74c3c;}"
            "QGroupBox::title { subcontrol-origin:margin; padding:2px 8px;}"
        )
        prev_lay = QVBoxLayout(prev_grp)
        self._anon_edit = QTextEdit()
        self._anon_edit.setReadOnly(True)
        self._anon_edit.setFixedHeight(120)
        self._anon_edit.setStyleSheet("font-size:11px; background:#fff8f8;")
        placeholder_lbl = QLabel(
            "← Klicke zuerst auf 'Anonymisierten Text generieren', "
            "prüfe ihn auf persönliche Daten, dann sende an Gemini."
        )
        placeholder_lbl.setStyleSheet("color:#888; font-size:10px;")
        placeholder_lbl.setWordWrap(True)
        prev_lay.addWidget(placeholder_lbl)
        self._anon_placeholder = placeholder_lbl
        prev_lay.addWidget(self._anon_edit)
        left_lay.addWidget(prev_grp)

        splitter.addWidget(left)

        # ── Rechte Seite: Gemini ─────────────────────────────────────────────
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setSpacing(8)

        # ─── Vorgaben-Box ────────────────────────────────────────────────────
        ctx_grp = QGroupBox("⚙️  Vorgaben für Gemini")
        ctx_lay = QVBoxLayout(ctx_grp)
        ctx_lay.setSpacing(5)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Länge:"))
        self._ctx_laenge = QComboBox()
        self._ctx_laenge.addItems([
            "Kurz (1–2 Absätze)",
            "Mittel (3–5 Absätze)",
            "Lang (ausführlich)",
            "Sehr ausführlich",
        ])
        self._ctx_laenge.setCurrentIndex(1)
        row1.addWidget(self._ctx_laenge)
        row1.addSpacing(16)
        row1.addWidget(QLabel("Ton:"))
        self._ctx_ton = QComboBox()
        self._ctx_ton.addItems([
            "Förmlich",
            "Neutral",
            "Informell",
            "Empathisch-förmlich",
        ])
        row1.addWidget(self._ctx_ton)
        row1.addStretch()
        ctx_lay.addLayout(row1)

        ctx_lay.addWidget(QLabel("Zusätzlicher Freitext-Kontext:"))
        self._ctx_freitext = QTextEdit()
        self._ctx_freitext.setFixedHeight(48)
        self._ctx_freitext.setPlaceholderText(
            "z.\u202fB. ‘Vorfall bereits eskaliert.’ · ‘Bitte Kulanz anbieten.’ …"
        )
        ctx_lay.addWidget(self._ctx_freitext)

        ctx_lay.addWidget(QLabel("<b>Maßnahmen zur Verbesserung ansprechen:</b>"))
        _MASSNAHMEN = [
            "Entschuldigung aussprechen",   "Kulanzlösung anbieten",
            "Erläuterung der Abläufe",     "Nachschulung des Personals",
            "Prozessverbesserung einleiten", "Rückruf anbieten",
            "Prüfung des Vorfalls zusagen",  "Vorfall intern eskalieren",
        ]
        self._massnahmen_checks: list[QCheckBox] = []
        mass_w = QWidget()
        mass_gl = QGridLayout(mass_w)
        mass_gl.setContentsMargins(0, 0, 0, 0)
        mass_gl.setSpacing(3)
        for _mi, _mn in enumerate(_MASSNAHMEN):
            _cb = QCheckBox(_mn)
            _cb.setStyleSheet("font-size:11px;")
            self._massnahmen_checks.append(_cb)
            mass_gl.addWidget(_cb, _mi // 2, _mi % 2)
        ctx_lay.addWidget(mass_w)
        right_lay.addWidget(ctx_grp)

        # ─── Gemini-Analyse ──────────────────────────────────────────────────
        gemini_grp = QGroupBox("🤖  Gemini-Analyse")
        g_lay = QVBoxLayout(gemini_grp)

        send_row = QHBoxLayout()
        self._btn_senden = _btn("🚀  An Gemini senden", "#900000", "#6b0000")
        self._btn_senden.setEnabled(False)
        self._btn_senden.setToolTip(
            "Erst anonymisierten Text generieren und prüfen, bevor an Gemini gesendet wird."
        )
        self._btn_senden.clicked.connect(self._send_to_gemini)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#555; font-size:11px;")
        send_row.addWidget(self._btn_senden)
        send_row.addWidget(self._status_lbl)
        send_row.addStretch()
        g_lay.addLayout(send_row)

        gem_hdr = QHBoxLayout()
        gem_hdr.addWidget(QLabel("<b>Gemini-Antwort:</b>"))
        gem_hdr.addStretch()
        btn_fullview = _btn("📋  Vollansicht", "#555", "#333")
        btn_fullview.setFixedWidth(115)
        btn_fullview.clicked.connect(self._open_gemini_fullview)
        gem_hdr.addWidget(btn_fullview)
        g_lay.addLayout(gem_hdr)
        self._gemini_result = QTextEdit()
        self._gemini_result.setReadOnly(True)
        self._gemini_result.setStyleSheet("font-size:12px; background:#fafeff;")
        self._gemini_result.setPlaceholderText("Hier erscheint die Gemini-Antwort …")
        g_lay.addWidget(self._gemini_result)

        btn_save_row = QHBoxLayout()
        btn_save = _btn("💾  In Beschwerde speichern", "#27ae60", "#1e8449")
        btn_save.clicked.connect(self._save_gemini_result)
        btn_save_row.addWidget(btn_save)
        btn_save_row.addStretch()
        g_lay.addLayout(btn_save_row)

        right_lay.addWidget(gemini_grp)
        splitter.addWidget(right)
        splitter.setSizes([480, 480])

        root.addWidget(splitter)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        root.addWidget(close_box)

    # ── Init: Extrahierte Werte als Checkboxen anzeigen ─────────────────────

    def _init_anon_items(self):
        text = self._beschwerde.get("originaltext", "")

        # Emails
        emails = _extrahiere_emails(text)
        # Immer auch die gespeicherte Email vorschlagen
        stored_email = self._beschwerde.get("email_beschwerdefuehrer", "").strip()
        if stored_email and stored_email not in emails:
            emails.insert(0, stored_email)
        for email in emails:
            cb = QCheckBox(email)
            cb.setChecked(True)
            self._email_check_lay.addWidget(cb)
            self._email_checks.append(cb)
        if not emails:
            self._email_check_lay.addWidget(QLabel("  (keine erkannt)"))

        # Namen
        namen = _extrahiere_namen(text)
        stored_name = self._beschwerde.get("name_beschwerdefuehrer", "").strip()
        if stored_name and stored_name not in namen:
            namen.insert(0, stored_name)
        for name in namen:
            cb = QCheckBox(name)
            cb.setChecked(True)
            self._name_check_lay.addWidget(cb)
            self._name_checks.append(cb)
        if not namen:
            self._name_check_lay.addWidget(QLabel("  (keine erkannt)"))

        # Telefonnummern
        telefone = _extrahiere_telefon(text)
        for tel in telefone:
            cb = QCheckBox(tel)
            cb.setChecked(True)
            self._tel_check_lay.addWidget(cb)
            self._tel_checks.append(cb)
        if not telefone:
            self._tel_check_lay.addWidget(QLabel("  (keine erkannt)"))

    # ── Schritt 1: Vorschau generieren ───────────────────────────────────────

    def _generate_preview(self):
        emails   = [cb.text() for cb in self._email_checks if cb.isChecked()]
        namen    = [cb.text() for cb in self._name_checks  if cb.isChecked()]
        telefone = [cb.text() for cb in self._tel_checks   if cb.isChecked()]
        extra    = self._extra_edit.toPlainText()

        text = self._beschwerde.get("originaltext", "")
        anon, mapping = _anonymisiere_text(text, emails, namen, telefone, extra)
        self._anon_text = anon

        self._anon_edit.setPlainText(anon)
        self._anon_placeholder.setVisible(False)

        # Jetzt erst Senden-Button freischalten
        self._btn_senden.setEnabled(True)
        self._btn_senden.setToolTip("Anonymisierten Text an Gemini senden.")

        if mapping:
            self._status_lbl.setText(
                f"✅ {len(mapping)} Ersetzung(en) vorgenommen — bitte Text prüfen!"
            )
        else:
            self._status_lbl.setText("ℹ️ Keine Ersetzungen — Text enthält keine markierten Begriffe.")

    # ── Schritt 2: An Gemini senden ──────────────────────────────────────────

    def _send_to_gemini(self):
        if not self._anon_text.strip():
            QMessageBox.warning(self, "Kein Text", "Bitte zuerst Vorschau generieren.")
            return
        self._btn_senden.setEnabled(False)
        self._status_lbl.setText("⏳  Sende an Gemini … (bis zu 3 Versuche bei Rate-Limit)")
        self._gemini_result.setPlainText("")

        sig = self._gemini_sig
        anon = self._anon_text
        massnahmen = [cb.text() for cb in self._massnahmen_checks if cb.isChecked()]
        freitext_user = self._ctx_freitext.toPlainText().strip()
        freitext_combined = freitext_user
        if massnahmen:
            freitext_combined += ("\n" if freitext_combined else "") + \
                "Bitte folgende Maßnahmen in der Antwort ansprechen: " + ", ".join(massnahmen) + "."
        kontext = {
            "laenge":   self._ctx_laenge.currentText(),
            "ton":      self._ctx_ton.currentText(),
            "freitext": freitext_combined,
        }

        def worker():
            try:
                result = _call_gemini(anon, kontext)
                sig.fertig.emit(result)
            except Exception as e:
                sig.fehler.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_gemini_fertig(self, text: str):
        self._gemini_result.setPlainText(text)
        self._status_lbl.setText("✅  Gemini-Antwort erhalten.")
        self._btn_senden.setEnabled(True)

    def _on_gemini_fehler(self, msg: str):
        self._status_lbl.setText(f"❌  Fehler: {msg[:80]}")
        self._btn_senden.setEnabled(True)
        QMessageBox.critical(self, "Gemini-Fehler", msg)

    def _save_gemini_result(self):
        result = self._gemini_result.toPlainText().strip()
        if not result:
            QMessageBox.warning(self, "Keine Antwort", "Noch keine Gemini-Antwort vorhanden.")
            return
        daten = dict(self._beschwerde)
        daten["gemini_antwort"] = result
        try:
            beschwerde_aktualisieren(self._beschwerde["id"], daten)
            QMessageBox.information(self, "Gespeichert", "Gemini-Antwort wurde gespeichert.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _open_gemini_fullview(self):
        text = self._gemini_result.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Leer", "Noch keine Gemini-Antwort vorhanden.")
            return
        _TextViewDialog("Gemini-Antwort", text, self).exec()


# ══════════════════════════════════════════════════════════════════════════════
#  Haupt-Widget
# ══════════════════════════════════════════════════════════════════════════════

class BeschwerdenWidget(QWidget):
    """Hauptseite für das Beschwerden-Management."""

    _COLS = [
        "ID", "Datum", "Name", "E-Mail", "Quelle",
        "Kategorie", "Priorität", "Status", "Text (Vorschau)",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._daten: list[dict] = []
        self._build()
        self._load()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📣  Beschwerden")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {FIORI_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._stat_lbl = QLabel("")
        self._stat_lbl.setStyleSheet("color:#777; font-size:11px;")
        hdr.addWidget(self._stat_lbl)
        root.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ddd;"); root.addWidget(sep)

        # Filterzeile
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Status:"))
        self._f_status = QComboBox()
        self._f_status.addItems(["Alle"] + STATUS_OPTIONEN)
        self._f_status.setFixedWidth(130)
        self._f_status.currentTextChanged.connect(self._load)
        filt.addWidget(self._f_status)

        filt.addWidget(QLabel("Priorität:"))
        self._f_prio = QComboBox()
        self._f_prio.addItems(["Alle"] + PRIORITAETEN)
        self._f_prio.setFixedWidth(110)
        self._f_prio.currentTextChanged.connect(self._load)
        filt.addWidget(self._f_prio)

        filt.addWidget(QLabel("Kategorie:"))
        self._f_kat = QComboBox()
        self._f_kat.addItems(["Alle"] + KATEGORIEN)
        self._f_kat.setFixedWidth(180)
        self._f_kat.currentTextChanged.connect(self._load)
        filt.addWidget(self._f_kat)

        filt.addWidget(QLabel("Suche:"))
        self._f_suche = QLineEdit()
        self._f_suche.setFixedWidth(180)
        self._f_suche.setPlaceholderText("Text / Name / E-Mail …")
        self._f_suche.returnPressed.connect(self._load)
        filt.addWidget(self._f_suche)

        btn_suche = _btn("🔍", "#555", "#333")
        btn_suche.setFixedWidth(36)
        btn_suche.clicked.connect(self._load)
        filt.addWidget(btn_suche)

        btn_reset = _btn("✕", "#999", "#777")
        btn_reset.setFixedWidth(36)
        btn_reset.setToolTip("Filter zurücksetzen")
        btn_reset.clicked.connect(self._reset_filter)
        filt.addWidget(btn_reset)
        filt.addStretch()
        root.addLayout(filt)

        # Toolbar
        tool = QHBoxLayout()
        self._btn_import    = _btn("➕  Neu / Import", FIORI_BLUE)
        self._btn_edit      = _btn("✏️  Bearbeiten", "#6c757d", "#5a6268")
        self._btn_antwort   = _btn("📧  Antworten", "#17a2b8", "#138496")
        self._btn_gemini    = _btn("🤖  Gemini-Analyse", "#6f42c1", "#5e35b1")
        self._btn_reasoning = _btn("🧠  Gemini Reasoning", "#8B5E3C", "#6B4530")
        self._btn_del       = _btn("🗑  Löschen", "#dc3545", "#c82333")

        for b in [self._btn_edit, self._btn_antwort, self._btn_gemini,
                  self._btn_reasoning, self._btn_del]:
            b.setEnabled(False)

        self._btn_import.clicked.connect(self._action_import)
        self._btn_edit.clicked.connect(self._action_edit)
        self._btn_antwort.clicked.connect(self._action_antwort)
        self._btn_gemini.clicked.connect(self._action_gemini)
        self._btn_reasoning.clicked.connect(self._action_reasoning)
        self._btn_del.clicked.connect(self._action_loeschen)

        btn_refresh = _btn("🔄", "#28a745", "#1e7e34")
        btn_refresh.setFixedWidth(36)
        btn_refresh.setToolTip("Daten neu laden")
        btn_refresh.clicked.connect(self._load)

        for b in [self._btn_import, self._btn_edit, self._btn_antwort,
                  self._btn_gemini, self._btn_reasoning, self._btn_del, btn_refresh]:
            tool.addWidget(b)
        tool.addStretch()
        root.addLayout(tool)

        # Tabelle
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd; border-radius: 6px;
                font-size: 12px; gridline-color: #eee;
            }
            QTableWidget::item:selected { background-color: #d0e8ff; color: #1a1a1a; }
            QHeaderView::section {
                background-color: #f0f4f8; color: #333;
                font-weight: bold; font-size: 11px;
                padding: 6px; border: none; border-bottom: 1px solid #ddd;
            }
        """)

        hdr_h = self._table.horizontalHeader()
        hdr_h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        hdr_h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        hdr_h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Name
        hdr_h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Email
        hdr_h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Quelle
        hdr_h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Kategorie
        hdr_h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Priorität
        hdr_h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Status
        hdr_h.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)           # Vorschau

        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.doubleClicked.connect(self._action_edit)

        # Vertikaler Splitter: Tabelle oben, Detail-Panel unten
        _vsplit = QSplitter(Qt.Orientation.Vertical)
        _vsplit.addWidget(self._table)
        _vsplit.addWidget(self._build_detail_panel())
        _vsplit.setSizes([360, 210])
        root.addWidget(_vsplit)

    # ── Datenladen & Anzeige ────────────────────────────────────────────────

    def _load(self):
        try:
            self._daten = lade_beschwerden(
                status=self._f_status.currentText() if hasattr(self, "_f_status") else "Alle",
                prioritaet=self._f_prio.currentText() if hasattr(self, "_f_prio") else "Alle",
                kategorie=self._f_kat.currentText() if hasattr(self, "_f_kat") else "Alle",
                suche=self._f_suche.text() if hasattr(self, "_f_suche") else "",
            )
        except Exception as e:
            QMessageBox.critical(self, "Datenbankfehler", str(e))
            self._daten = []
        self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(0)
        self._update_detail(None)  # Detail-Panel leeren beim Neuladen
        for d in self._daten:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, _ro_item(str(d["id"])))
            self._table.setItem(row, 1, _ro_item(d.get("datum_eingang", "")))
            self._table.setItem(row, 2, _ro_item(d.get("name_beschwerdefuehrer", "")))
            self._table.setItem(row, 3, _ro_item(d.get("email_beschwerdefuehrer", "")))
            self._table.setItem(row, 4, _ro_item(d.get("quelle", "")))
            self._table.setItem(row, 5, _ro_item(d.get("kategorie", "")))

            prio = d.get("prioritaet", "Mittel")
            bg_p, fg_p = _PRIO_FARBEN.get(prio, ("#999", "white"))
            self._table.setItem(row, 6, _badge_item(prio, bg_p, fg_p))

            stat = d.get("status", "Offen")
            bg_s, fg_s = _STATUS_FARBEN.get(stat, ("#999", "white"))
            self._table.setItem(row, 7, _badge_item(stat, bg_s, fg_s))

            vorschau = (d.get("originaltext", "") or "").replace("\n", " ")[:80]
            self._table.setItem(row, 8, _ro_item(vorschau))

            self._table.setRowHeight(row, 36)

        offen = sum(1 for d in self._daten if d.get("status") == "Offen")
        self._stat_lbl.setText(
            f"{len(self._daten)} Einträge  |  {offen} offen"
        )
        self._update_buttons()

    def _reset_filter(self):
        self._f_status.setCurrentIndex(0)
        self._f_prio.setCurrentIndex(0)
        self._f_kat.setCurrentIndex(0)
        self._f_suche.clear()
        self._load()

    # ── Selektion ───────────────────────────────────────────────────────────

    def _on_selection(self):
        self._update_buttons()
        self._update_detail(self._selected_daten())

    def _update_buttons(self):
        sel = self._table.currentRow() >= 0 and bool(self._table.selectedItems())
        for b in [self._btn_edit, self._btn_antwort, self._btn_gemini,
                  self._btn_reasoning, self._btn_del]:
            b.setEnabled(sel)

    def _selected_daten(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._daten):
            return None
        return self._daten[row]

    # ── Aktionen ────────────────────────────────────────────────────────────

    def _action_import(self):
        dlg = _ImportDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                beschwerde_speichern(dlg.get_daten())
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    def _action_edit(self):
        d = self._selected_daten()
        if not d:
            return
        dlg = _BeschwerdeEditDialog(d, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                beschwerde_aktualisieren(d["id"], dlg.get_daten())
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    def _action_antwort(self):
        d = self._selected_daten()
        if not d:
            return
        _AntwortDialog(d, parent=self).exec()
        self._load()

    def _action_gemini(self):
        d = self._selected_daten()
        if not d:
            return
        if not d.get("originaltext", "").strip():
            QMessageBox.warning(
                self, "Kein Text",
                "Diese Beschwerde hat keinen Originaltext.\n"
                "Bitte zuerst Text importieren oder eingeben.",
            )
            return
        dlg = _GeminiDialog(d, parent=self)
        dlg.exec()
        self._load()

    def _action_reasoning(self):
        d = self._selected_daten()
        if not d:
            return
        if not d.get("originaltext", "").strip():
            QMessageBox.warning(
                self, "Kein Text",
                "Diese Beschwerde hat keinen Originaltext.\n"
                "Bitte zuerst Text importieren oder eingeben.",
            )
            return
        dlg = _GeminiReasoningDialog(d, parent=self)
        dlg.exec()
        self._load()

    def _action_loeschen(self):
        d = self._selected_daten()
        if not d:
            return
        reply = QMessageBox.question(
            self, "Löschen bestätigen",
            f"Beschwerde #{d['id']} wirklich löschen?\n(Alle zugehörigen Antworten werden ebenfalls gelöscht.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                beschwerde_loeschen(d["id"])
                self._load()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", str(e))

    # ── Detail-Panel: Aufbau ────────────────────────────────────────────────

    def _build_detail_panel(self) -> QWidget:
        """Erstellt das Detail-Panel (3 Tabs) unterhalb der Tabelle."""
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(0)

        self._detail_tabs = QTabWidget()
        self._detail_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #f8f9fa; }
            QTabBar::tab {
                padding: 6px 14px;
                font-size: 11px;
                font-family: 'Segoe UI';
                color: #666;
                background: #e8ecf0;
                border-bottom: 2px solid transparent;
                border-radius: 4px 4px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #f8f9fa;
                color: #1565a8;
                font-weight: bold;
                border-bottom: 2px solid #1565a8;
            }
            QTabBar::tab:hover:!selected {
                background: #dde4ec;
                color: #1565a8;
            }
        """)

        # ── Tab 0: Originaltext ────────────────────────────────────────────
        ow = QWidget()
        olay = QVBoxLayout(ow)
        olay.setContentsMargins(6, 6, 6, 6)
        ohdr = QHBoxLayout()
        ohdr.addWidget(QLabel("<b>Originaltext:</b>"))
        ohdr.addStretch()
        btn_orig = _btn("📋  Vollansicht", "#555", "#333")
        btn_orig.setFixedWidth(115)
        btn_orig.clicked.connect(
            lambda: self._open_text_popup("Originaltext", self._detail_orig.toPlainText())
        )
        ohdr.addWidget(btn_orig)
        olay.addLayout(ohdr)
        self._detail_orig = QTextEdit()
        self._detail_orig.setReadOnly(True)
        self._detail_orig.setStyleSheet("font-size:12px; background:#fafafa;")
        olay.addWidget(self._detail_orig)
        self._detail_tabs.addTab(ow, "📄  Originaltext")

        # ── Tab 1: Gemini-Antwort ──────────────────────────────────────────
        gw = QWidget()
        glay = QVBoxLayout(gw)
        glay.setContentsMargins(6, 6, 6, 6)
        ghdr = QHBoxLayout()
        ghdr.addWidget(QLabel("<b>Gemini-Antwort:</b>"))
        ghdr.addStretch()
        btn_gem = _btn("📋  Vollansicht", "#6f42c1", "#5e35b1")
        btn_gem.setFixedWidth(115)
        btn_gem.clicked.connect(
            lambda: self._open_text_popup("Gemini-Antwort", self._detail_gemini.toPlainText())
        )
        ghdr.addWidget(btn_gem)
        glay.addLayout(ghdr)
        self._detail_gemini = QTextEdit()
        self._detail_gemini.setReadOnly(True)
        self._detail_gemini.setStyleSheet("font-size:12px; background:#fafeff;")
        glay.addWidget(self._detail_gemini)
        self._detail_tabs.addTab(gw, "🤖  Gemini-Antwort")

        # ── Tab 2: Antwort-Verlauf ─────────────────────────────────────────
        hw = QWidget()
        hlay = QVBoxLayout(hw)
        hlay.setContentsMargins(6, 6, 6, 6)
        self._detail_hist = QWidget()
        self._detail_hist_lay = QVBoxLayout(self._detail_hist)
        self._detail_hist_lay.setContentsMargins(0, 0, 0, 0)
        self._detail_hist_lay.setSpacing(4)
        hscroll = QScrollArea()
        hscroll.setWidget(self._detail_hist)
        hscroll.setWidgetResizable(True)
        hscroll.setStyleSheet("QScrollArea { border: none; }")
        hlay.addWidget(hscroll)
        self._detail_tabs.addTab(hw, "📧  Antwort-Verlauf")

        lay.addWidget(self._detail_tabs)
        return panel

    # ── Detail-Panel: Daten ─────────────────────────────────────────────────

    def _update_detail(self, d: dict | None):
        """Befüllt das Detail-Panel für den gewählten Tabelleneintrag."""
        if not hasattr(self, "_detail_orig"):
            return
        if d is None:
            self._detail_orig.clear()
            self._detail_gemini.clear()
            self._clear_hist_panel()
            return
        self._detail_orig.setPlainText(d.get("originaltext", ""))
        self._detail_gemini.setPlainText(d.get("gemini_antwort", ""))
        self._clear_hist_panel()
        try:
            antworten = lade_antworten(d["id"])
        except Exception:
            antworten = []
        if not antworten:
            lbl = QLabel("  (Noch keine Antworten vorhanden)")
            lbl.setStyleSheet("color:#888; font-size:11px; padding:8px;")
            self._detail_hist_lay.addWidget(lbl)
        else:
            for a in antworten:
                self._detail_hist_lay.addWidget(self._make_answer_card(a))
        self._detail_hist_lay.addStretch()

    def _clear_hist_panel(self):
        """Entfernt alle Widgets und Spacer aus dem Verlauf-Layout."""
        while self._detail_hist_lay.count():
            item = self._detail_hist_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _make_answer_card(self, a: dict) -> QFrame:
        """Erstellt eine kompakte Karte für eine gespeicherte Antwort."""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background:#f0f8ff; border:1px solid #bee3f8;"
            " border-radius:5px; }"
        )
        c_lay = QHBoxLayout(card)
        c_lay.setContentsMargins(10, 6, 10, 6)
        info = QVBoxLayout()
        info.setSpacing(2)
        top = QLabel(f"<b>{a.get('datum', '—')}</b>  →  {a.get('empfaenger', '')}")
        top.setStyleSheet("font-size:11px; color:#333;")
        info.addWidget(top)
        raw = a.get("antworttext", "") or ""
        prev = raw.replace("\n", " ")[:120] + ("…" if len(raw) > 120 else "")
        prev_lbl = QLabel(prev)
        prev_lbl.setStyleSheet("font-size:11px; color:#666;")
        prev_lbl.setWordWrap(True)
        info.addWidget(prev_lbl)
        c_lay.addLayout(info, 1)
        btn = _btn("📖  Lesen", "#17a2b8", "#138496")
        btn.setFixedWidth(90)
        _t, _d = raw, a.get("datum", "")
        btn.clicked.connect(lambda _, t=_t, dat=_d: self._open_text_popup(f"Antwort vom {dat}", t))
        c_lay.addWidget(btn)
        return card

    def _open_text_popup(self, title: str, text: str):
        """Öffnet einen Vollansichts-Dialog für beliebige Texte."""
        if not text.strip():
            QMessageBox.information(self, "Leer", "Kein Text vorhanden.")
            return
        _TextViewDialog(title, text, parent=self).exec()
