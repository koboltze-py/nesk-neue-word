"""
Schulungen-Kalender-Widget
Großer Monatskalender mit farbkodierten Ablaufterminen für Mitarbeiter-Schulungen.
Farben: Gelb (3 Monate), Orange (2 Monate), Rot (1 Monat), Dunkelrot (abgelaufen).
"""
import calendar
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDateEdit, QTextEdit, QScrollArea, QSizePolicy, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QGroupBox, QCheckBox, QProgressDialog,
)
from PySide6.QtCore import Qt, QDate, QSize, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QCursor

from config import FIORI_BLUE

# ─── Farb-Konstanten ──────────────────────────────────────────────────────────
_FARBEN = {
    "abgelaufen": ("#b71c1c", "#ffffff"),   # bg, text
    "rot":        ("#e53935", "#ffffff"),
    "orange":     ("#ef6c00", "#ffffff"),
    "gelb":       ("#f9a825", "#000000"),
    "ok":         ("#2e7d32", "#ffffff"),
    "einmalig":   ("#546e7a", "#ffffff"),   # done-once, no expiry
}
_ZELL_BG = {
    "abgelaufen": "#ffebee",
    "rot":        "#fff3e0",
    "orange":     "#fff8e1",
    "gelb":       "#fffde7",
}
_WICHTIGKEIT = ["abgelaufen", "rot", "orange", "gelb", "ok", "einmalig", ""]


def _chip_farbe(dring: str) -> tuple[str, str]:
    return _FARBEN.get(dring, ("#90a4ae", "#ffffff"))


def _btn(text: str, color: str = FIORI_BLUE, hover: str = "#0057b8",
         height: int = 30) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(height)
    b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:#fff;border:none;"
        f"border-radius:4px;padding:2px 12px;font-size:12px;}}"
        f"QPushButton:hover{{background:{hover};}}"
    )
    return b


def _btn_flat(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(28)
    b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    b.setStyleSheet(
        "QPushButton{background:#eceff1;color:#333;border:none;"
        "border-radius:4px;padding:2px 10px;font-size:12px;}"
        "QPushButton:hover{background:#cfd8dc;}"
    )
    return b


# ─── Kalender-Zelle ───────────────────────────────────────────────────────────
class _TagZelle(QFrame):
    """Eine einzelne Tageszelle im Kalender."""
    geklickt = Signal(date, list)   # emittiert (datum, eintraege)

    MAX_CHIPS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._datum: date | None = None
        self._eintraege: list = []
        self._ist_heute = False
        self._anderer_monat = False
        self.setFixedHeight(100)
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._tag_lbl = QLabel()
        self._tag_lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        layout.addWidget(self._tag_lbl)

        self._chips_layout = QVBoxLayout()
        self._chips_layout.setSpacing(1)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._chips_layout)
        layout.addStretch()

    def setze_datum(self, d: date | None, eintraege: list, anderer_monat: bool = False):
        self._datum          = d
        self._eintraege      = eintraege
        self._ist_heute      = (d == date.today()) if d else False
        self._anderer_monat  = anderer_monat
        self._aktualisieren()

    def _aktualisieren(self):
        # Chips löschen
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._datum is None:
            self.setStyleSheet("QFrame{background:#f5f5f5;border:1px solid #e0e0e0;border-radius:4px;}")
            self._tag_lbl.setText("")
            return

        # Hintergrundfarbe je nach dringlichstem Eintrag
        dringlichkeiten = [e.get("_dringlichkeit", "") for e in self._eintraege]
        dring_bg = ""
        for d_key in _WICHTIGKEIT:
            if d_key in dringlichkeiten:
                dring_bg = d_key
                break

        bg = _ZELL_BG.get(dring_bg, "#ffffff")
        if self._anderer_monat:
            bg = "#f9f9f9"
        rand = "#1565c0" if self._ist_heute else "#e0e0e0"
        rand_w = "2" if self._ist_heute else "1"
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:{rand_w}px solid {rand};"
            f"border-radius:4px;}}"
        )

        # Tag-Nummer
        txt = str(self._datum.day)
        farbe = "#1565c0" if self._ist_heute else ("#999" if self._anderer_monat else "#333")
        self._tag_lbl.setText(txt)
        self._tag_lbl.setStyleSheet(f"color:{farbe};background:transparent;")

        # Chips
        zeige = self._eintraege[:self.MAX_CHIPS]
        for e in zeige:
            chip = self._chip_label(e)
            self._chips_layout.addWidget(chip)
        rest = len(self._eintraege) - self.MAX_CHIPS
        if rest > 0:
            mehr = QLabel(f"  +{rest} weitere")
            mehr.setStyleSheet("color:#666;font-size:9px;background:transparent;")
            self._chips_layout.addWidget(mehr)

    def _chip_label(self, eintrag: dict) -> QLabel:
        dring = eintrag.get("_dringlichkeit", "")
        bg, fg = _chip_farbe(dring)
        typ  = SCHULUNGSTYP_KURZ.get(eintrag.get("schulungstyp",""), eintrag.get("schulungstyp","")[:6])
        name = eintrag.get("_name", "?")
        text = f"  {name[:14]} · {typ}"
        lbl  = QLabel(text)
        lbl.setStyleSheet(
            f"QLabel{{background:{bg};color:{fg};border-radius:3px;"
            f"font-size:9px;padding:1px 2px;}}"
        )
        lbl.setToolTip(
            f"{eintrag.get('_name')} – {SCHULUNGSTYPEN_CFG_K.get(eintrag.get('schulungstyp',''),{}).get('anzeige','')}\n"
            f"Gültig bis: {eintrag.get('gueltig_bis','?')}"
        )
        return lbl

    def mousePressEvent(self, ev):
        if self._datum and self._eintraege:
            self.geklickt.emit(self._datum, self._eintraege)
        super().mousePressEvent(ev)


# ─── Monats-Kalender-Grid ─────────────────────────────────────────────────────
class _MonatsKalender(QWidget):
    tagesklick = Signal(date, list)

    WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jahr  = date.today().year
        self._monat = date.today().month
        self._daten: dict = {}   # date → [eintrag, ...]
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        # Wochentag-Header
        header = QHBoxLayout()
        header.setSpacing(4)
        for wt in self.WOCHENTAGE:
            lbl = QLabel(wt)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(24)
            lbl.setStyleSheet(
                f"QLabel{{background:{'#1565c0' if wt in ('Sa','So') else FIORI_BLUE};"
                "color:#fff;border-radius:3px;font-size:11px;font-weight:bold;}}"
            )
            header.addWidget(lbl)
        v.addLayout(header)

        # Tageszellen (6 Zeilen × 7 Spalten)
        self._zellen: list[list[_TagZelle]] = []
        for row in range(6):
            zeile = []
            hl = QHBoxLayout()
            hl.setSpacing(4)
            for col in range(7):
                z = _TagZelle()
                z.geklickt.connect(self.tagesklick.emit)
                hl.addWidget(z)
                zeile.append(z)
            v.addLayout(hl)
            self._zellen.append(zeile)

        self._render()

    def setze_monat(self, jahr: int, monat: int, daten: dict):
        self._jahr  = jahr
        self._monat = monat
        self._daten = daten
        self._render()

    def _render(self):
        cal = calendar.monthcalendar(self._jahr, self._monat)
        # calendar.monthcalendar kann 4-6 Zeilen haben, wir haben immer 6
        while len(cal) < 6:
            cal.append([0, 0, 0, 0, 0, 0, 0])

        for r, woche in enumerate(cal[:6]):
            for c, tag_nr in enumerate(woche):
                zelle = self._zellen[r][c]
                if tag_nr == 0:
                    zelle.setze_datum(None, [], False)
                else:
                    try:
                        d = date(self._jahr, self._monat, tag_nr)
                    except ValueError:
                        zelle.setze_datum(None, [], False)
                        continue
                    eintraege = self._daten.get(d, [])
                    zelle.setze_datum(d, eintraege, False)


# ─── Tages-Detail-Dialog ──────────────────────────────────────────────────────
class _TagesDetailDialog(QDialog):
    def __init__(self, d: date, eintraege: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"📅 {d.strftime('%d. %B %Y')} – Ablaufende Schulungen")
        self.resize(560, 380)
        v = QVBoxLayout(self)
        v.setSpacing(10)

        titel = QLabel(f"Ablaufende Schulungen am {d.strftime('%d.%m.%Y')}:")
        titel.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        v.addWidget(titel)

        tbl = QTableWidget()
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["Mitarbeiter", "Schulungsart", "Gültig bis", "Status"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setAlternatingRowColors(True)
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tbl.verticalHeader().setVisible(False)
        tbl.setRowCount(len(eintraege))

        for row, e in enumerate(eintraege):
            dring = e.get("_dringlichkeit", "")
            bg, _ = _chip_farbe(dring)
            cfg_an = SCHULUNGSTYPEN_CFG_K.get(e.get("schulungstyp",""), {}).get("anzeige", e.get("schulungstyp",""))
            daten = [
                e.get("_name", ""),
                cfg_an,
                e.get("gueltig_bis", ""),
                e.get("status", ""),
            ]
            for col, text in enumerate(daten):
                item = QTableWidgetItem(text)
                item.setBackground(QColor(bg + "44"))
                tbl.setItem(row, col, item)
        v.addWidget(tbl)

        btn = _btn("Schließen", "#546e7a", "#455a64")
        btn.clicked.connect(self.accept)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# ─── Neuer-Mitarbeiter-Dialog ─────────────────────────────────────────────────
class NeuerMitarbeiterDialog(QDialog):
    """
    Dialog zum Anlegen eines neuen Mitarbeiters – inklusive
    Schulungsdaten und optionalem Sync in mitarbeiter.db / nesk3.db.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("👤 Neuer Mitarbeiter anlegen")
        self.setMinimumWidth(620)
        self.resize(680, 780)
        self._result_ma    = {}
        self._result_syncs = {}
        self._build_ui()

    def _build_ui(self):
        from functions.mitarbeiter_sync import (
            lade_positionen_ma_db, lade_abteilungen_ma_db
        )
        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.setContentsMargins(16, 16, 16, 12)

        titel = QLabel("👤 Neuen Mitarbeiter anlegen")
        titel.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        titel.setStyleSheet(f"color:{FIORI_BLUE};")
        v.addWidget(titel)

        tabs = QTabWidget()
        v.addWidget(tabs)

        # ── Tab 1: Stammdaten ──────────────────────────────────────────────
        t1 = QWidget()
        f1 = QFormLayout(t1)
        f1.setSpacing(8)
        f1.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._nachname     = QLineEdit(); self._nachname.setPlaceholderText("Nachname *")
        self._vorname      = QLineEdit(); self._vorname.setPlaceholderText("Vorname *")
        self._geburtsdatum = QDateEdit(QDate(1990, 1, 1))
        self._geburtsdatum.setCalendarPopup(True)
        self._geburtsdatum.setDisplayFormat("dd.MM.yyyy")
        self._anstellung   = QComboBox()
        self._anstellung.addItems(["NA", "Hauptamt", "FSJ", "Praktikant", "Sonstiges"])
        self._qualifikation = QComboBox()
        self._qualifikation.setEditable(True)
        self._qualifikation.addItems(["PRM", "RS", "NotSan", "FSJ", "SB", "Sonstiges"])
        self._bemerkung_ma = QTextEdit()
        self._bemerkung_ma.setMaximumHeight(70)
        self._bemerkung_ma.setPlaceholderText("Interne Bemerkung …")

        f1.addRow("Nachname *:", self._nachname)
        f1.addRow("Vorname *:", self._vorname)
        f1.addRow("Geburtsdatum:", self._geburtsdatum)
        f1.addRow("Anstellung:", self._anstellung)
        f1.addRow("Qualifikation:", self._qualifikation)
        f1.addRow("Bemerkung:", self._bemerkung_ma)
        tabs.addTab(t1, "👤 Stammdaten")

        # ── Tab 2: Schulungen ──────────────────────────────────────────────
        t2 = QWidget()
        f2 = QFormLayout(t2)
        f2.setSpacing(8)
        f2.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _date_edit(special="— (noch nicht absolviert)"):
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd.MM.yyyy")
            w.setSpecialValueText(special)
            w.setMinimumDate(QDate(2000, 1, 1))
            w.setDate(QDate(2000, 1, 1))
            return w

        self._zuep_bis       = _date_edit(); f2.addRow("ZÜP gültig bis:", self._zuep_bis)
        self._eh_datum       = _date_edit(); f2.addRow("EH (letztes Datum):", self._eh_datum)
        self._refresher      = _date_edit(); f2.addRow("Refresher (letztes Datum):", self._refresher)
        self._aerztl_bis     = _date_edit(); f2.addRow("Ärztl. Untersuchung gültig bis:", self._aerztl_bis)
        self._fuehr_kont     = _date_edit(); f2.addRow("Führerschein Kontrolle:", self._fuehr_kont)
        self._arbeitsschutz  = _date_edit(); f2.addRow("Arbeitsschutz:", self._arbeitsschutz)
        tabs.addTab(t2, "🎓 Schulungen")

        # ── Tab 3: Weitere Infos (für andere DBs) ─────────────────────────
        t3 = QWidget()
        f3 = QFormLayout(t3)
        f3.setSpacing(8)
        f3.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._personalnr  = QLineEdit(); self._personalnr.setPlaceholderText("Optional")
        self._funktion    = QComboBox()
        self._funktion.setEditable(True)
        self._funktion.addItems(["PRM", "Schichtleiter", "SB", "Fahrer", "Sonstiges"])
        self._position    = QComboBox()
        self._position.setEditable(True)
        pos = lade_positionen_ma_db()
        self._position.addItems(pos if pos else ["PRM", "Schichtleiter"])
        self._abteilung   = QComboBox()
        self._abteilung.setEditable(True)
        abt = lade_abteilungen_ma_db()
        self._abteilung.addItems(abt if abt else ["Passagierbetreuung"])
        self._email       = QLineEdit(); self._email.setPlaceholderText("max.mustermann@drk-koeln.de")
        self._telefon     = QLineEdit(); self._telefon.setPlaceholderText("0221 / …")
        self._eintrittsd  = QDateEdit(QDate.currentDate())
        self._eintrittsd.setCalendarPopup(True)
        self._eintrittsd.setDisplayFormat("dd.MM.yyyy")

        f3.addRow("Personalnummer:", self._personalnr)
        f3.addRow("Funktion:", self._funktion)
        f3.addRow("Position:", self._position)
        f3.addRow("Abteilung:", self._abteilung)
        f3.addRow("E-Mail:", self._email)
        f3.addRow("Telefon:", self._telefon)
        f3.addRow("Eintrittsdatum:", self._eintrittsd)
        tabs.addTab(t3, "📋 Mitarbeiterdaten")

        # ── Sync-Optionen ──────────────────────────────────────────────────
        sync_frame = QFrame()
        sync_frame.setStyleSheet(
            "QFrame{background:#e3f2fd;border:1px solid #90caf9;"
            "border-radius:4px;padding:4px;}"
        )
        sf = QHBoxLayout(sync_frame)
        info = QLabel("Auch anlegen in:")
        info.setStyleSheet("font-weight:bold;color:#1565c0;")
        sf.addWidget(info)
        self._sync_ma   = QCheckBox("mitarbeiter.db")
        self._sync_ma.setChecked(True)
        self._sync_nesk = QCheckBox("nesk3.db")
        self._sync_nesk.setChecked(True)
        sf.addWidget(self._sync_ma)
        sf.addWidget(self._sync_nesk)
        sf.addStretch()
        v.addWidget(sync_frame)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_speichern = _btn("💾  Speichern", "#2e7d32", "#1b5e20", 34)
        self._btn_speichern.clicked.connect(self._speichern)
        btn_abbrechen = _btn_flat("Abbrechen")
        btn_abbrechen.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_speichern)
        btn_row.addWidget(btn_abbrechen)
        v.addLayout(btn_row)

    def _speichern(self):
        if not self._nachname.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte Nachname eingeben.")
            return
        if not self._vorname.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte Vorname eingeben.")
            return
        self.accept()

    def _datum_oder_leer(self, widget: "QDateEdit") -> str:
        d = widget.date()
        if d == QDate(2000, 1, 1):
            return ""
        return d.toString("dd.MM.yyyy")

    def _datum_obj(self, widget: "QDateEdit"):
        from datetime import date as _date
        d = widget.date()
        if d == QDate(2000, 1, 1):
            return None
        return _date(d.year(), d.month(), d.day())

    def get_stamm_daten(self) -> dict:
        geb = self._geburtsdatum.date()
        return {
            "nachname":     self._nachname.text().strip(),
            "vorname":      self._vorname.text().strip(),
            "geburtsdatum": geb.toString("dd.MM.yyyy"),
            "anstellung":   self._anstellung.currentText(),
            "qualifikation":self._qualifikation.currentText(),
            "bemerkung":    self._bemerkung_ma.toPlainText().strip(),
        }

    def get_schulungs_daten(self) -> dict:
        """Gibt Schulungseinträge-Rohdaten zurück (gueltig_bis als String)."""
        from functions.schulungen_db import _berechne_gueltig_bis, _datum_str
        from datetime import date as _date
        def _d(w): return w.date() if w.date() != QDate(2000, 1, 1) else None
        def _ds(qd): return _date(qd.year(), qd.month(), qd.day()) if qd else None

        eintraege = {}

        def _add(key, datum_absolviert_qd, gueltig_bis_qd=None):
            d_abs   = _ds(_d(datum_absolviert_qd))
            d_gb    = _ds(_d(gueltig_bis_qd)) if gueltig_bis_qd else None
            gb_calc = _berechne_gueltig_bis(key, d_abs, d_gb or d_abs)
            if d_abs or d_gb:
                eintraege[key] = {
                    "schulungstyp":     key,
                    "datum_absolviert": _datum_str(d_abs),
                    "gueltig_bis":      _datum_str(gb_calc or d_gb),
                }

        _add("ZÜP",                 None, self._zuep_bis)
        _add("EH",                  self._eh_datum)
        _add("Refresher",           self._refresher)
        _add("Aerztl_Untersuchung", None, self._aerztl_bis)
        _add("Fuehrerschein_Kont",  self._fuehr_kont)
        _add("Arbeitsschutz",       self._arbeitsschutz)
        return eintraege

    def get_ma_db_daten(self) -> dict:
        return {
            "personalnummer": self._personalnr.text().strip(),
            "funktion":       self._funktion.currentText(),
            "position":       self._position.currentText(),
            "abteilung":      self._abteilung.currentText(),
            "email":          self._email.text().strip(),
            "telefon":        self._telefon.text().strip(),
            "eintrittsdatum": self._eintrittsd.date().toString("dd.MM.yyyy"),
        }

    def sync_aktiviert_ma(self)   -> bool: return self._sync_ma.isChecked()
    def sync_aktiviert_nesk(self) -> bool: return self._sync_nesk.isChecked()


# ─── Schulungstyp-Kurznahmen (für Chips) ─────────────────────────────────────
# Späte Imports aus schulungen_db –  wird zur Laufzeit befüllt
SCHULUNGSTYP_KURZ: dict = {}
SCHULUNGSTYPEN_CFG_K: dict = {}


def _lade_typen():
    global SCHULUNGSTYP_KURZ, SCHULUNGSTYPEN_CFG_K
    try:
        from functions.schulungen_db import SCHULUNGSTYPEN_CFG
        SCHULUNGSTYPEN_CFG_K = SCHULUNGSTYPEN_CFG
        SCHULUNGSTYP_KURZ = {
            "ZÜP":                 "ZÜP",
            "EH":                  "EH",
            "Refresher":           "Ref.",
            "Aerztl_Untersuchung": "Ärztl.",
            "Fuehrerschein_Kont":  "FS-Kont.",
            "Einw_Zertifikate":    "Zert.",
            "Fixierung":           "Fix.",
            "Einw_eMobby":         "e-Mobby",
            "Bulmor":              "Bulmor",
            "Arbeitsschutz":       "ArbSchut.",
            "Einw_QM":             "QM",
            "Fragebogen_Schulung": "Frageb.",
            "Personalausweis":     "PA/Pass",
            "Sonstiges":           "Sonst.",
        }
    except Exception:
        pass


# ─── Agenda-Liste ─────────────────────────────────────────────────────────────
class _AgendaWidget(QWidget):
    """Liste der nächsten ablaufenden Schulungen (nächste 3 Monate)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        hdr = QLabel("⚠️  Bald ablaufende Schulungen (nächste 3 Monate)")
        hdr.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{FIORI_BLUE};")
        v.addWidget(hdr)

        self._tbl = QTableWidget()
        self._tbl.setColumnCount(5)
        self._tbl.setHorizontalHeaderLabels(
            ["Mitarbeiter", "Schulungsart", "Gültig bis", "Tage", "Status"]
        )
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setStyleSheet("font-size:12px;")
        self._tbl.verticalHeader().setVisible(False)
        v.addWidget(self._tbl)

    def aktualisieren(self):
        from functions.schulungen_db import lade_ablaufende, SCHULUNGSTYPEN_CFG
        try:
            eintraege = lade_ablaufende(3)
        except Exception as exc:
            self._tbl.setRowCount(0)
            return

        # Sortierung: abgelaufen zuerst, dann nach Tagen
        priori = {"abgelaufen": -1, "rot": 0, "orange": 1, "gelb": 2, "ok": 3}
        eintraege.sort(key=lambda e: (priori.get(e.get("_dringlichkeit",""), 9),
                                       e.get("_tage_rest", 9999)))
        self._tbl.setRowCount(len(eintraege))
        FARB_MAP = {
            "abgelaufen": "#ffcdd2",
            "rot":        "#ffe0b2",
            "orange":     "#fff9c4",
            "gelb":       "#f9fbe7",
        }
        for row, e in enumerate(eintraege):
            dring = e.get("_dringlichkeit", "")
            bg    = FARB_MAP.get(dring, "#ffffff")
            cfg   = SCHULUNGSTYPEN_CFG.get(e.get("schulungstyp",""), {})
            anzeige = cfg.get("anzeige", e.get("schulungstyp",""))
            tage    = e.get("_tage_rest", 0)
            tage_txt = f"{tage} Tage" if tage >= 0 else f"ÜBERFÄLLIG {-tage}d"
            vals = [
                e.get("_name", ""),
                anzeige,
                e.get("gueltig_bis", ""),
                tage_txt,
                e.get("status", ""),
            ]
            for col, text in enumerate(vals):
                item = QTableWidgetItem(text)
                item.setBackground(QColor(bg))
                if col == 3 and tage < 0:
                    item.setForeground(QColor("#b71c1c"))
                self._tbl.setItem(row, col, item)


# ─── Haupt-Widget ─────────────────────────────────────────────────────────────
class SchulungenKalenderWidget(QWidget):
    """
    Großes Kalender-Widget für den Schulungen-Tab.
    Zeigt monatliche Übersicht + Agenda-Liste + Import/Anlegen-Buttons.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        _lade_typen()
        self._jahr  = date.today().year
        self._monat = date.today().month
        self._build_ui()
        # Einmaliger Auto-Import beim ersten Start (wenn DB noch leer)
        try:
            from functions.schulungen_db import erstimport_wenn_leer
            erstimport_wenn_leer()
        except Exception:
            pass
        self._aktualisieren()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(8)

        # ── Steuerleiste ───────────────────────────────────────────────────
        ctrl = QFrame()
        ctrl.setStyleSheet(
            "QFrame{background:#e8f5e9;border:1px solid #a5d6a7;"
            "border-radius:4px;}"
        )
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(10, 6, 10, 6)
        cl.setSpacing(10)

        btn_prev = _btn("◀", "#546e7a", "#455a64", 32)
        btn_prev.setFixedWidth(36)
        btn_prev.clicked.connect(self._vorheriger_monat)

        self._monat_lbl = QLabel()
        self._monat_lbl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self._monat_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._monat_lbl.setMinimumWidth(180)

        btn_next = _btn("▶", "#546e7a", "#455a64", 32)
        btn_next.setFixedWidth(36)
        btn_next.clicked.connect(self._naechster_monat)

        btn_heute = _btn_flat("Heute")
        btn_heute.clicked.connect(self._gehe_zu_heute)

        cl.addWidget(btn_prev)
        cl.addWidget(self._monat_lbl)
        cl.addWidget(btn_next)
        cl.addWidget(btn_heute)
        cl.addStretch()

        self._btn_import = _btn("📥  Excel importieren", "#1565c0", "#0d47a1", 32)
        self._btn_import.clicked.connect(self._excel_importieren)
        self._btn_neuer_ma = _btn("👤  Neuer Mitarbeiter", "#2e7d32", "#1b5e20", 32)
        self._btn_neuer_ma.clicked.connect(self._neuer_mitarbeiter)
        cl.addWidget(self._btn_import)
        cl.addWidget(self._btn_neuer_ma)
        v.addWidget(ctrl)

        # ── Legende ────────────────────────────────────────────────────────
        leg = QHBoxLayout()
        leg.setSpacing(8)
        for key, label in [
            ("abgelaufen", "Abgelaufen"),
            ("rot", "≤ 1 Monat"),
            ("orange", "≤ 2 Monate"),
            ("gelb", "≤ 3 Monate"),
            ("ok", "OK"),
        ]:
            bg, fg = _chip_farbe(key)
            lbl = QLabel(f"  {label}  ")
            lbl.setStyleSheet(
                f"QLabel{{background:{bg};color:{fg};border-radius:4px;"
                f"font-size:11px;padding:2px 6px;}}"
            )
            leg.addWidget(lbl)
        leg.addStretch()
        v.addLayout(leg)

        # ── Splitter: Kalender oben, Agenda unten ──────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Kalender
        self._kalender = _MonatsKalender()
        self._kalender.tagesklick.connect(self._tag_geklickt)
        splitter.addWidget(self._kalender)

        # Agenda
        self._agenda = _AgendaWidget()
        splitter.addWidget(self._agenda)

        splitter.setSizes([480, 260])
        v.addWidget(splitter, 1)

    def _aktualisieren(self):
        from functions.schulungen_db import lade_kalender_daten
        monate_de = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ]
        self._monat_lbl.setText(f"{monate_de[self._monat]} {self._jahr}")
        try:
            daten = lade_kalender_daten(self._jahr, self._monat)
        except Exception:
            daten = {}
        self._kalender.setze_monat(self._jahr, self._monat, daten)
        self._agenda.aktualisieren()

    def _vorheriger_monat(self):
        if self._monat == 1:
            self._monat = 12
            self._jahr -= 1
        else:
            self._monat -= 1
        self._aktualisieren()

    def _naechster_monat(self):
        if self._monat == 12:
            self._monat = 1
            self._jahr += 1
        else:
            self._monat += 1
        self._aktualisieren()

    def _gehe_zu_heute(self):
        heute = date.today()
        self._jahr  = heute.year
        self._monat = heute.month
        self._aktualisieren()

    def _tag_geklickt(self, d: date, eintraege: list):
        dlg = _TagesDetailDialog(d, eintraege, self)
        dlg.exec()

    def _excel_importieren(self):
        from PySide6.QtWidgets import QFileDialog
        from functions.schulungen_db import excel_importieren, _EXCEL_PFAD
        pfad, _ = QFileDialog.getOpenFileName(
            self, "Excel-Stammdatei auswählen",
            str(_EXCEL_PFAD.parent),
            "Excel (*.xlsx *.xls)"
        )
        if not pfad:
            return
        prog = QProgressDialog("Importiere …", None, 0, 0, self)
        prog.setWindowTitle("Excel-Import")
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.show()
        try:
            imp, skip = excel_importieren(pfad)
            prog.close()
            QMessageBox.information(
                self, "Import abgeschlossen",
                f"✅ Erfolgreich importiert: {imp} Mitarbeiter\n"
                f"⏭ Übersprungen (leer): {skip}"
            )
            self._aktualisieren()
        except ImportError as e:
            prog.close()
            QMessageBox.critical(self, "Fehler", str(e))
        except Exception as e:
            prog.close()
            QMessageBox.critical(self, "Import-Fehler", str(e))

    def _neuer_mitarbeiter(self):
        from functions.schulungen_db import (
            speichere_mitarbeiter, speichere_schulungseintrag,
            SCHULUNGSTYPEN_CFG, _berechne_status
        )
        from functions.mitarbeiter_sync import sync_neuer_mitarbeiter
        from datetime import date as _date

        dlg = NeuerMitarbeiterDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        stamm  = dlg.get_stamm_daten()
        schul  = dlg.get_schulungs_daten()
        ma_dat = dlg.get_ma_db_daten()

        try:
            # 1. Mitarbeiter-Stamm in schulungen.db
            ma_id = speichere_mitarbeiter(stamm)

            # 2. Schulungseinträge
            now = datetime.now().isoformat(timespec="seconds")
            for key, s in schul.items():
                cfg = SCHULUNGSTYPEN_CFG.get(key, {})
                from functions.schulungen_db import _parse_datum, _berechne_status as _bs
                gb = _parse_datum(s.get("gueltig_bis"))
                speichere_schulungseintrag({
                    "mitarbeiter_id":  ma_id,
                    "schulungstyp":    key,
                    "datum_absolviert": s.get("datum_absolviert",""),
                    "gueltig_bis":     s.get("gueltig_bis",""),
                    "laeuft_nicht_ab": int(cfg.get("laeuft_nicht_ab", False)),
                    "status":          _bs(gb, cfg.get("laeuft_nicht_ab", False)),
                    "bemerkung":       "",
                })

            # 3. Sync in andere DBs
            sync_cfg = {}
            if dlg.sync_aktiviert_ma():
                sync_cfg["mitarbeiter.db"] = True
            if dlg.sync_aktiviert_nesk():
                sync_cfg["nesk3.db"] = True

            ergebnis = sync_neuer_mitarbeiter(stamm, ma_dat)
            meldungen = [f"✅ schulungen.db – Mitarbeiter + {len(schul)} Schulungseinträge"]
            for db, ok in ergebnis.items():
                if db == "mitarbeiter.db" and not dlg.sync_aktiviert_ma():
                    continue
                if db == "nesk3.db" and not dlg.sync_aktiviert_nesk():
                    continue
                meldungen.append(f"{'✅' if ok else '⏭'} {db} – {'angelegt' if ok else 'bereits vorhanden'}")

            QMessageBox.information(
                self, "Mitarbeiter angelegt",
                f"{stamm['nachname']}, {stamm['vorname']} wurde erfolgreich angelegt.\n\n"
                + "\n".join(meldungen)
            )
            self._aktualisieren()

        except Exception as exc:
            QMessageBox.critical(self, "Fehler beim Anlegen", str(exc))
