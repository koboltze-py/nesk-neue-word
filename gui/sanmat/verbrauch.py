"""
VerbrauchView – Zeigt alle Verbrauch-Buchungen aus Einsätzen.
Gefilterte Ansicht des Buchungsverlaufs (typ='verbrauch').
"""

from __future__ import annotations
import csv
import os
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QDateEdit, QFileDialog,
    QMessageBox, QFrame,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from database.sanmat_db import SanmatDB

PAGE_SIZE = 100


class VerbrauchView(QWidget):
    """Zeigt alle Verbrauch-Buchungen (Einsatz-Verbrauch) mit Filter und CSV-Export."""

    _HDR = ["Datum", "Artikel", "Menge", "Entnehmer", "Bemerkung"]

    def __init__(self, db: SanmatDB, parent=None):
        super().__init__(parent)
        self._db = db
        self._page = 0
        self._total = 0
        self._setup_ui()
        self._laden()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Titel
        title = QLabel("🧰  Einsatz-Verbrauch")
        title.setStyleSheet("font-size:16px; font-weight:bold; color:#1565a8;")
        root.addWidget(title)

        sub = QLabel("Verbrauchsmaterial aus Einsätzen – aus Sanmat-Bestand abgebucht.")
        sub.setStyleSheet("color:#666; font-size:11px;")
        root.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ddd;")
        root.addWidget(sep)

        # Filter-Zeile
        f_lay = QHBoxLayout()
        f_lay.setSpacing(8)

        f_lay.addWidget(QLabel("Von:"))
        self._von = QDateEdit()
        self._von.setCalendarPopup(True)
        self._von.setDisplayFormat("dd.MM.yyyy")
        self._von.setDate(QDate(QDate.currentDate().year(), 1, 1))
        self._von.setFixedWidth(120)
        f_lay.addWidget(self._von)

        f_lay.addWidget(QLabel("Bis:"))
        self._bis = QDateEdit()
        self._bis.setCalendarPopup(True)
        self._bis.setDisplayFormat("dd.MM.yyyy")
        self._bis.setDate(QDate.currentDate())
        self._bis.setFixedWidth(120)
        f_lay.addWidget(self._bis)

        self._suche = QLineEdit()
        self._suche.setPlaceholderText("Entnehmer oder Artikel suchen …")
        self._suche.setFixedWidth(200)
        self._suche.returnPressed.connect(self._on_filter)
        f_lay.addWidget(self._suche)

        btn_filter = QPushButton("🔍 Filtern")
        btn_filter.clicked.connect(self._on_filter)
        f_lay.addWidget(btn_filter)

        btn_reset = QPushButton("↺ Zurücksetzen")
        btn_reset.clicked.connect(self._reset_filter)
        f_lay.addWidget(btn_reset)

        f_lay.addStretch()

        btn_export = QPushButton("📄 CSV Export")
        btn_export.clicked.connect(self._export_csv)
        f_lay.addWidget(btn_export)

        root.addLayout(f_lay)

        # Tabelle
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._HDR))
        self._table.setHorizontalHeaderLabels(self._HDR)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, 1)

        # Paginierung
        pg_lay = QHBoxLayout()
        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet("color:#555; font-size:11px;")
        pg_lay.addWidget(self._lbl_info)
        pg_lay.addStretch()
        self._btn_prev = QPushButton("◀ Zurück")
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_next = QPushButton("Weiter ▶")
        self._btn_next.clicked.connect(self._next_page)
        pg_lay.addWidget(self._btn_prev)
        pg_lay.addWidget(self._btn_next)
        root.addLayout(pg_lay)

    # ── Laden ────────────────────────────────────────────────────────────────

    def _laden(self):
        von_str = self._von.date().toString("yyyy-MM-dd")
        bis_str = self._bis.date().toString("yyyy-MM-dd")
        suche   = self._suche.text().strip() or None

        self._total = self._db.count_buchungen(typ="verbrauch", datum_von=von_str, datum_bis=bis_str, suche=suche)
        rows = self._db.get_buchungen(
            limit=PAGE_SIZE, offset=self._page * PAGE_SIZE,
            typ="verbrauch", datum_von=von_str, datum_bis=bis_str, suche=suche
        )
        self._table.setRowCount(len(rows))
        for r, b in enumerate(rows):
            # Datum formatieren
            datum_raw = b.get("datum", "")[:10]
            try:
                y, mo, d = datum_raw.split("-")
                datum_fmt = f"{d}.{mo}.{y}"
            except Exception:
                datum_fmt = datum_raw

            menge = abs(b.get("menge", 0))
            vals = [
                datum_fmt,
                b.get("artikel_name", ""),
                str(menge),
                b.get("von", ""),
                b.get("bemerkung", ""),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 2:
                    item.setForeground(QColor("#c0392b"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)

        pages = max(1, (self._total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._lbl_info.setText(f"{self._total} Einträge  |  Seite {self._page + 1} / {pages}")
        self._btn_prev.setEnabled(self._page > 0)
        self._btn_next.setEnabled((self._page + 1) * PAGE_SIZE < self._total)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_filter(self):
        self._page = 0
        self._laden()

    def _reset_filter(self):
        self._von.setDate(QDate(QDate.currentDate().year(), 1, 1))
        self._bis.setDate(QDate.currentDate())
        self._suche.clear()
        self._page = 0
        self._laden()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._laden()

    def _next_page(self):
        if (self._page + 1) * PAGE_SIZE < self._total:
            self._page += 1
            self._laden()

    def _export_csv(self):
        pfad, _ = QFileDialog.getSaveFileName(
            self, "CSV speichern", f"sanmat_verbrauch_{date.today()}.csv", "CSV (*.csv)"
        )
        if not pfad:
            return
        von_str = self._von.date().toString("yyyy-MM-dd")
        bis_str = self._bis.date().toString("yyyy-MM-dd")
        suche   = self._suche.text().strip() or None
        alle = self._db.get_buchungen(limit=99999, offset=0, typ="verbrauch",
                                      datum_von=von_str, datum_bis=bis_str, suche=suche)
        try:
            with open(pfad, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(self._HDR)
                for b in alle:
                    datum_raw = b.get("datum", "")[:10]
                    try:
                        y, mo, d = datum_raw.split("-")
                        datum_fmt = f"{d}.{mo}.{y}"
                    except Exception:
                        datum_fmt = datum_raw
                    w.writerow([
                        datum_fmt,
                        b.get("artikel_name", ""),
                        abs(b.get("menge", 0)),
                        b.get("von", ""),
                        b.get("bemerkung", ""),
                    ])
            QMessageBox.information(self, "Export", f"CSV gespeichert:\n{pfad}")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e))

    def showEvent(self, event):
        super().showEvent(event)
        self._laden()
