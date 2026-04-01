"""
Sanitätsmaterial – Artikel-Stammdatenverwaltung
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QCheckBox,
    QDialog, QDialogButtonBox, QFormLayout, QTextEdit,
    QMessageBox, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

_KATEGORIEN = [
    "Desinfektion", "Diagnostik", "Entsorgung", "Notfallausrüstung",
    "Patientenversorgung", "Schutzausrüstung", "Verbrauchsmaterial", "Wundversorgung",
]
_EINHEITEN = ["Stück", "Pck.", "Fl.", "Rolle", "Set", "Paar", "Kin.", "Kan.", "Karton"]


class ArtikelDialog(QDialog):
    def __init__(self, db, item: dict = None, parent=None):
        super().__init__(parent)
        self.db = db
        self._item = item
        self.setWindowTitle("Artikel bearbeiten" if item else "Neuer Artikel")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._setup_ui()
        if item:
            self._fill(item)

    def _setup_ui(self):
        form = QFormLayout(self)
        form.setSpacing(10)
        form.setContentsMargins(20, 20, 20, 16)

        self.le_artikelnr = QLineEdit()
        self.le_artikelnr.setPlaceholderText("z.B. 9422041")
        form.addRow("Artikelnummer:", self.le_artikelnr)

        self.le_bezeichnung = QLineEdit()
        self.le_bezeichnung.setPlaceholderText("Pflichtfeld")
        form.addRow("Bezeichnung *:", self.le_bezeichnung)

        self.cb_kat = QComboBox()
        self.cb_kat.addItem("")
        self.cb_kat.addItems(_KATEGORIEN)
        form.addRow("Kategorie:", self.cb_kat)

        self.cb_einheit = QComboBox()
        self.cb_einheit.setEditable(True)
        self.cb_einheit.addItems(_EINHEITEN)
        form.addRow("Einheit:", self.cb_einheit)

        self.le_packungsinhalt = QLineEdit()
        self.le_packungsinhalt.setPlaceholderText("z.B. 100 Stück")
        form.addRow("Packungsinhalt:", self.le_packungsinhalt)

        self.le_hersteller = QLineEdit("meetB")
        form.addRow("Hersteller:", self.le_hersteller)

        self.le_pzn = QLineEdit()
        self.le_pzn.setPlaceholderText("PZN ...")
        form.addRow("PZN:", self.le_pzn)

        self.le_bemerkung = QLineEdit()
        form.addRow("Bemerkung:", self.le_bemerkung)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Speichern")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _fill(self, item: dict):
        self.le_artikelnr.setText(item.get("artikelnr", ""))
        self.le_bezeichnung.setText(item.get("bezeichnung", ""))
        kat = item.get("kategorie", "")
        idx = self.cb_kat.findText(kat)
        self.cb_kat.setCurrentIndex(idx if idx >= 0 else 0)
        ein = item.get("einheit", "Stück")
        idx_e = self.cb_einheit.findText(ein)
        if idx_e >= 0:
            self.cb_einheit.setCurrentIndex(idx_e)
        else:
            self.cb_einheit.setCurrentText(ein)
        self.le_packungsinhalt.setText(item.get("packungsinhalt", ""))
        self.le_hersteller.setText(item.get("hersteller", "meetB"))
        self.le_pzn.setText(item.get("pzn", ""))
        self.le_bemerkung.setText(item.get("bemerkung", ""))

    def _validate(self):
        if not self.le_bezeichnung.text().strip():
            QMessageBox.warning(self, "Pflichtfeld", "Bitte eine Bezeichnung eingeben.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "bezeichnung":    self.le_bezeichnung.text().strip(),
            "artikelnr":      self.le_artikelnr.text().strip(),
            "kategorie":      self.cb_kat.currentText(),
            "einheit":        self.cb_einheit.currentText(),
            "packungsinhalt": self.le_packungsinhalt.text().strip(),
            "hersteller":     self.le_hersteller.text().strip(),
            "pzn":            self.le_pzn.text().strip(),
            "bemerkung":      self.le_bemerkung.text().strip(),
        }


class ArtikelView(QWidget):
    COLS = ["Artikelnr.", "Bezeichnung", "Kategorie", "Einheit", "Packungsinhalt", "Hersteller", "PZN"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        lbl_title = QLabel("Artikel-Stammdaten")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Alle verwalteten Sanitätsmaterial-Artikel")
        lbl_sub.setObjectName("page_subtitle")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.le_suche = QLineEdit()
        self.le_suche.setPlaceholderText("Suche nach Bezeichnung, Artikelnr. ...")
        self.le_suche.setClearButtonEnabled(True)
        self.le_suche.textChanged.connect(self._load)
        filter_row.addWidget(self.le_suche, stretch=2)

        self.cb_kat = QComboBox()
        self.cb_kat.addItem("Alle Kategorien")
        self.cb_kat.addItems(_KATEGORIEN)
        self.cb_kat.currentIndexChanged.connect(self._load)
        filter_row.addWidget(self.cb_kat)

        self.chk_inaktiv = QCheckBox("Inaktive anzeigen")
        self.chk_inaktiv.stateChanged.connect(self._load)
        filter_row.addWidget(self.chk_inaktiv)

        filter_row.addStretch()

        btn_neu = QPushButton("＋  Neuer Artikel")
        btn_neu.setObjectName("btn_primary")
        btn_neu.clicked.connect(self._neu)
        filter_row.addWidget(btn_neu)
        layout.addLayout(filter_row)

        # Tabelle
        self._tbl = QTableWidget(0, len(self.COLS))
        self._tbl.setHorizontalHeaderLabels(self.COLS)
        self._tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in [0, 2, 3, 4, 5, 6]:
            self._tbl.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tbl.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self._tbl)

        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(self._lbl_count)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_edit = QPushButton("✏  Bearbeiten")
        btn_edit.setObjectName("btn_secondary")
        btn_edit.clicked.connect(self._edit_selected)
        btn_row.addWidget(btn_edit)
        btn_deak = QPushButton("Deaktivieren")
        btn_deak.setObjectName("btn_danger")
        btn_deak.clicked.connect(self._deactivate)
        btn_row.addWidget(btn_deak)
        layout.addLayout(btn_row)

    def _load(self):
        suche = self.le_suche.text().lower()
        kat = self.cb_kat.currentText()
        nur_aktiv = not self.chk_inaktiv.isChecked()
        artikel = self.db.get_artikel(nur_aktiv=nur_aktiv)

        def _match(a):
            if kat != "Alle Kategorien" and a.get("kategorie", "") != kat:
                return False
            if suche:
                h = (a.get("bezeichnung", "") + " " + a.get("artikelnr", "") +
                     " " + a.get("kategorie", "")).lower()
                return suche in h
            return True

        filtered = [a for a in artikel if _match(a)]
        self._tbl.setRowCount(len(filtered))
        for r, a in enumerate(filtered):
            vals = [
                a.get("artikelnr", ""), a.get("bezeichnung", ""),
                a.get("kategorie", ""), a.get("einheit", ""),
                a.get("packungsinhalt", ""), a.get("hersteller", ""), a.get("pzn", ""),
            ]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if not a.get("aktiv", 1):
                    it.setForeground(QColor("#AAAAAA"))
                it.setData(Qt.ItemDataRole.UserRole, a.get("id"))
                self._tbl.setItem(r, c, it)
        self._lbl_count.setText(f"{len(filtered)} Artikel")

    def _get_selected_id(self) -> int | None:
        row = self._tbl.currentRow()
        if row < 0:
            return None
        item = self._tbl.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _neu(self):
        dlg = ArtikelDialog(self.db, parent=self)
        if dlg.exec():
            _, msg = self.db.add_artikel(**dlg.get_data())
            QMessageBox.information(self, "Angelegt", msg)
            self._load()

    def _edit_selected(self):
        aid = self._get_selected_id()
        if not aid:
            QMessageBox.information(self, "Hinweis", "Bitte erst einen Artikel auswählen.")
            return
        item = self.db.get_artikel_by_id(aid)
        if not item:
            return
        dlg = ArtikelDialog(self.db, item=item, parent=self)
        if dlg.exec():
            ok, msg = self.db.update_artikel(aid, **dlg.get_data())
            if ok:
                QMessageBox.information(self, "Gespeichert", msg)
            else:
                QMessageBox.warning(self, "Fehler", msg)
            self._load()

    def _deactivate(self):
        aid = self._get_selected_id()
        if not aid:
            QMessageBox.information(self, "Hinweis", "Bitte erst einen Artikel auswählen.")
            return
        reply = QMessageBox.question(
            self, "Deaktivieren",
            "Artikel wirklich deaktivieren? Er bleibt in der Datenbank, wird aber ausgeblendet.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.db.deactivate_artikel(aid)
            if ok:
                self._load()
            else:
                QMessageBox.warning(self, "Fehler", msg)

    def showEvent(self, event):
        super().showEvent(event)
        self._load()
