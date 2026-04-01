"""
Sanitätsmaterial – Entnahme & Verbrauch
Material entnehmen oder als verbraucht buchen.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QGroupBox, QFormLayout, QMessageBox, QHeaderView, QAbstractItemView,
    QFrame, QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor


class EntnahmeView(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._artikel_liste: list[dict] = []
        self._warenkorb: list[dict] = []
        self._setup_ui()
        self._load_artikel()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        lbl_title = QLabel("Entnahme / Verbrauch")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Artikel suchen, auswählen und Menge buchen")
        lbl_sub.setObjectName("page_subtitle")
        root.addWidget(lbl_title)
        root.addWidget(lbl_sub)

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        # Linke Spalte: Artikelsuche
        left = QVBoxLayout()
        left.setSpacing(6)
        lbl_suche = QLabel("Artikel suchen")
        lbl_suche.setStyleSheet("font-weight:bold; font-size:13px;")
        left.addWidget(lbl_suche)

        self._le_suche = QLineEdit()
        self._le_suche.setPlaceholderText("Name, Artikelnummer oder Kategorie …")
        self._le_suche.setClearButtonEnabled(True)
        self._le_suche.setStyleSheet("padding:6px 8px; font-size:13px;")
        self._le_suche.textChanged.connect(self._filter_artikel)
        left.addWidget(self._le_suche)

        self._tbl_artikel = QTableWidget()
        self._tbl_artikel.setColumnCount(3)
        self._tbl_artikel.setHorizontalHeaderLabels(["Bezeichnung", "Art.-Nr.", "Verfügbar"])
        self._tbl_artikel.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl_artikel.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_artikel.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_artikel.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl_artikel.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_artikel.setAlternatingRowColors(True)
        self._tbl_artikel.verticalHeader().setVisible(False)
        self._tbl_artikel.setMinimumWidth(420)
        self._tbl_artikel.setMinimumHeight(320)
        self._tbl_artikel.doubleClicked.connect(self._artikel_hinzufuegen)
        self._tbl_artikel.setStyleSheet("QTableWidget{font-size:13px;}")
        left.addWidget(self._tbl_artikel)

        btn_add = QPushButton("+ Ausgewählten Artikel hinzufügen")
        btn_add.setObjectName("btn_secondary")
        btn_add.clicked.connect(self._artikel_hinzufuegen)
        left.addWidget(btn_add)
        main_row.addLayout(left, 3)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#ddd;")
        main_row.addWidget(sep)

        # Rechte Spalte: Warenkorb
        right = QVBoxLayout()
        right.setSpacing(6)
        lbl_korb = QLabel("Ausgewählte Positionen")
        lbl_korb.setStyleSheet("font-weight:bold; font-size:13px;")
        right.addWidget(lbl_korb)

        self._tbl_korb = QTableWidget()
        self._tbl_korb.setColumnCount(4)
        self._tbl_korb.setHorizontalHeaderLabels(["Artikel", "Verf.", "Menge", ""])
        self._tbl_korb.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl_korb.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl_korb.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._tbl_korb.setColumnWidth(2, 72)
        self._tbl_korb.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._tbl_korb.setColumnWidth(3, 36)
        self._tbl_korb.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tbl_korb.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_korb.verticalHeader().setVisible(False)
        self._tbl_korb.setMinimumWidth(380)
        self._tbl_korb.setMinimumHeight(320)
        right.addWidget(self._tbl_korb)

        self._lbl_korb_leer = QLabel("Noch keine Artikel ausgewählt.\nDoppelklick oder Schaltfläche.")
        self._lbl_korb_leer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_korb_leer.setStyleSheet("color:#999; font-size:12px; padding:20px;")
        right.addWidget(self._lbl_korb_leer)
        main_row.addLayout(right, 2)
        root.addLayout(main_row)

        # Buchungsinfo
        grp_meta = QGroupBox("Buchungsinfo")
        meta_lay = QHBoxLayout(grp_meta)
        meta_lay.setContentsMargins(16, 12, 16, 12)
        meta_lay.setSpacing(24)

        self._typ_group = QButtonGroup(self)
        self._rb_entnahme = QRadioButton("Entnahme")
        self._rb_verbrauch = QRadioButton("Verbrauch")
        self._rb_entnahme.setChecked(True)
        self._typ_group.addButton(self._rb_entnahme)
        self._typ_group.addButton(self._rb_verbrauch)
        typ_box = QVBoxLayout()
        typ_box.setSpacing(4)
        typ_box.addWidget(QLabel("Typ:"))
        typ_box.addWidget(self._rb_entnahme)
        typ_box.addWidget(self._rb_verbrauch)
        meta_lay.addLayout(typ_box)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
        meta_lay.addWidget(sep2)

        datum_box = QFormLayout()
        datum_box.setSpacing(8)
        self.de_datum = QDateEdit(QDate.currentDate())
        self.de_datum.setDisplayFormat("dd.MM.yyyy")
        self.de_datum.setCalendarPopup(True)
        self.de_datum.setFixedWidth(140)
        datum_box.addRow("Datum:", self.de_datum)
        meta_lay.addLayout(datum_box)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.VLine)
        meta_lay.addWidget(sep3)

        info_form = QFormLayout()
        info_form.setSpacing(8)
        self.le_von = QLineEdit()
        self.le_von.setPlaceholderText("Kürzel / Name")
        self.le_von.setFixedWidth(200)
        info_form.addRow("Entnommen von:", self.le_von)
        self.le_bem = QLineEdit()
        self.le_bem.setPlaceholderText("Patient, Einsatz … (optional)")
        self.le_bem.setMinimumWidth(260)
        info_form.addRow("Bemerkung:", self.le_bem)
        meta_lay.addLayout(info_form)
        meta_lay.addStretch()
        root.addWidget(grp_meta)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_reset = QPushButton("Zurücksetzen")
        btn_reset.setObjectName("btn_secondary")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)
        self._btn_buchen = QPushButton("✓  Buchen")
        self._btn_buchen.setObjectName("btn_primary")
        self._btn_buchen.setMinimumWidth(160)
        self._btn_buchen.clicked.connect(self._buchen)
        btn_row.addWidget(self._btn_buchen)
        root.addLayout(btn_row)

    def _load_artikel(self):
        self._artikel_liste = self.db.get_artikel()
        self._filter_artikel()

    def _filter_artikel(self):
        suchtext = self._le_suche.text().strip().lower()
        treffer = [
            a for a in self._artikel_liste
            if not suchtext
            or suchtext in a["bezeichnung"].lower()
            or suchtext in (a.get("artikelnr") or "").lower()
            or suchtext in (a.get("kategorie") or "").lower()
        ]
        self._tbl_artikel.setRowCount(0)
        for a in treffer:
            row = self._tbl_artikel.rowCount()
            self._tbl_artikel.insertRow(row)
            self._tbl_artikel.setRowHeight(row, 28)
            self._tbl_artikel.setItem(row, 0, QTableWidgetItem(a["bezeichnung"]))
            self._tbl_artikel.setItem(row, 1, QTableWidgetItem(a.get("artikelnr", "")))
            menge = int(a.get("menge", 0))
            einheit = a.get("einheit", "")
            verf_item = QTableWidgetItem(f"{menge} {einheit}".strip())
            verf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            verf_item.setForeground(QColor("#C62828") if menge == 0 else QColor("#2E7D32"))
            self._tbl_artikel.setItem(row, 2, verf_item)
            self._tbl_artikel.item(row, 0).setData(Qt.ItemDataRole.UserRole, a["id"])

    def _artikel_hinzufuegen(self):
        rows = self._tbl_artikel.selectionModel().selectedRows()
        if not rows:
            return
        for idx in rows:
            aid = self._tbl_artikel.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole)
            a = next((x for x in self._artikel_liste if x["id"] == aid), None)
            if not a:
                continue
            vorhanden = next((w for w in self._warenkorb if w["artikel"]["id"] == aid), None)
            if vorhanden:
                vorhanden["menge"] += 1
            else:
                self._warenkorb.append({"artikel": a, "menge": 1})
        self._refresh_korb()

    def _refresh_korb(self):
        leer = len(self._warenkorb) == 0
        self._tbl_korb.setVisible(not leer)
        self._lbl_korb_leer.setVisible(leer)
        self._tbl_korb.setRowCount(0)
        for i, eintrag in enumerate(self._warenkorb):
            a = eintrag["artikel"]
            self._tbl_korb.insertRow(i)
            self._tbl_korb.setRowHeight(i, 36)
            item_bez = QTableWidgetItem(a["bezeichnung"])
            item_bez.setToolTip(a.get("artikelnr", ""))
            self._tbl_korb.setItem(i, 0, item_bez)
            menge_verf = int(a.get("menge", 0))
            einheit = a.get("einheit", "")
            verf_item = QTableWidgetItem(f"{menge_verf} {einheit}".strip())
            verf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            verf_item.setForeground(QColor("#C62828") if menge_verf == 0 else QColor("#2E7D32"))
            self._tbl_korb.setItem(i, 1, verf_item)
            sb = QSpinBox()
            sb.setRange(1, 99999)
            sb.setValue(eintrag["menge"])
            sb.setMinimumWidth(68)
            sb.setMinimumHeight(30)
            sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            idx_cap = i
            sb.valueChanged.connect(lambda v, idx=idx_cap: self._korb_menge(idx, v))
            self._tbl_korb.setCellWidget(i, 2, sb)
            btn_x = QPushButton("×")
            btn_x.setMinimumHeight(30)
            btn_x.setStyleSheet("QPushButton{color:#B20000;font-weight:bold;font-size:16px;"
                                "border:none;background:transparent;}"
                                "QPushButton:hover{background:#fce4e4;border-radius:3px;}")
            idx_cap = i
            btn_x.clicked.connect(lambda _, idx=idx_cap: self._korb_entfernen(idx))
            self._tbl_korb.setCellWidget(i, 3, btn_x)

    def _korb_menge(self, idx: int, wert: int):
        if 0 <= idx < len(self._warenkorb):
            self._warenkorb[idx]["menge"] = wert

    def _korb_entfernen(self, idx: int):
        if 0 <= idx < len(self._warenkorb):
            self._warenkorb.pop(idx)
            self._refresh_korb()

    def _get_typ(self) -> str:
        return "verbrauch" if self._rb_verbrauch.isChecked() else "entnahme"

    def _buchen(self):
        if not self._warenkorb:
            QMessageBox.warning(self, "Kein Artikel", "Bitte mindestens einen Artikel auswählen.")
            return
        datum = self.de_datum.date().toString("yyyy-MM-dd")
        von = self.le_von.text().strip()
        bem = self.le_bem.text().strip()
        typ = self._get_typ()
        ok_list, err_list = [], []
        for eintrag in self._warenkorb:
            a = eintrag["artikel"]
            ok, msg = self.db.entnehmen(a["id"], a["bezeichnung"], eintrag["menge"], datum, typ, von, bem)
            (ok_list if ok else err_list).append(msg)
        msgs = []
        if ok_list:
            msgs.append("✓ " + "\n✓ ".join(ok_list))
        if err_list:
            msgs.append("✗ " + "\n✗ ".join(err_list))
        QMessageBox.information(self, "Buchung abgeschlossen", "\n".join(msgs))
        if ok_list:
            self._reset()

    def _reset(self):
        self._rb_entnahme.setChecked(True)
        self.de_datum.setDate(QDate.currentDate())
        self.le_von.clear()
        self.le_bem.clear()
        self._le_suche.clear()
        self._warenkorb.clear()
        self._refresh_korb()
        self._load_artikel()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_artikel()
