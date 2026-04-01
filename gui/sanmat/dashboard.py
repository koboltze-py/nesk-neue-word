"""
Sanitätsmaterial – Dashboard
Übersicht: Statistik-Karten, Kalender, Niedrigbestand-Tabelle.
"""

import time
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QGridLayout, QCalendarWidget, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QFont, QColor


class _StatCard(QWidget):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setObjectName("stat_card")
        self.setStyleSheet(f"""
            QWidget#stat_card {{
                background: white;
                border-left: 4px solid {color};
                border-radius: 4px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self._lbl_title = QLabel(title)
        self._lbl_title.setStyleSheet("color:#666; font-size:11px; font-weight:normal;")
        self._lbl_val = QLabel("–")
        self._lbl_val.setStyleSheet(f"color:{color}; font-size:28px; font-weight:bold;")
        layout.addWidget(self._lbl_title)
        layout.addWidget(self._lbl_val)

    def set_value(self, val):
        self._lbl_val.setText(str(val))


class DashboardView(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()
        self._refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Titel
        lbl_title = QLabel("Sanitätsmaterial  –  Dashboard")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Übersicht des aktuellen Bestands der Ersten-Hilfe-Station")
        lbl_sub.setObjectName("page_subtitle")
        root.addWidget(lbl_title)
        root.addWidget(lbl_sub)

        # Uhrzeit
        self._lbl_uhr = QLabel()
        self._lbl_uhr.setStyleSheet("font-size:13px; color:#555;")
        root.addWidget(self._lbl_uhr)

        # Statistik-Karten (Zeile)
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._card_gesamt  = _StatCard("Aktive Artikel",    "#0a6ed1")
        self._card_niedrig = _StatCard("Niedrigbestand",    "#e9730c")
        self._card_leer    = _StatCard("Leer",              "#bb0000")
        self._card_heute   = _StatCard("Buchungen heute",   "#107e3e")
        for c in [self._card_gesamt, self._card_niedrig, self._card_leer, self._card_heute]:
            c.setMinimumWidth(160)
            cards_row.addWidget(c)
        cards_row.addStretch()
        root.addLayout(cards_row)

        # Hauptbereich: Kalender + Niedrigbestand-Tabelle
        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        # Kalender
        self._cal = QCalendarWidget()
        self._cal.setGridVisible(True)
        self._cal.setMinimumWidth(300)
        self._cal.setMaximumWidth(360)
        self._cal.setNavigationBarVisible(True)
        main_row.addWidget(self._cal)

        # Niedrigbestand-Tabelle
        niedrig_col = QVBoxLayout()
        niedrig_col.setSpacing(8)
        lbl_niedrig = QLabel("Niedrigbestand – sofort nachbestellen")
        lbl_niedrig.setStyleSheet("font-weight:bold; font-size:13px; color:#e9730c;")
        niedrig_col.addWidget(lbl_niedrig)

        self._tbl_niedrig = QTableWidget(0, 5)
        self._tbl_niedrig.setHorizontalHeaderLabels(
            ["Bezeichnung", "Kategorie", "Auf Lager", "Mindest", "Lagerort"]
        )
        self._tbl_niedrig.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            self._tbl_niedrig.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self._tbl_niedrig.verticalHeader().setVisible(False)
        self._tbl_niedrig.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl_niedrig.setAlternatingRowColors(True)
        self._tbl_niedrig.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        niedrig_col.addWidget(self._tbl_niedrig)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄  Aktualisieren")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._refresh)
        btn_row.addWidget(btn_refresh)

        btn_min5 = QPushButton("Mindestbestand auf 5 setzen (Neue)")
        btn_min5.setObjectName("btn_secondary")
        btn_min5.clicked.connect(self._set_min5)
        btn_row.addWidget(btn_min5)
        btn_row.addStretch()
        niedrig_col.addLayout(btn_row)

        main_row.addLayout(niedrig_col, 1)
        root.addLayout(main_row, 1)

    def _tick(self):
        now = datetime.now()
        self._lbl_uhr.setText(now.strftime("%A, %d.%m.%Y   %H:%M:%S"))

    def _refresh(self):
        if not self.db.sanmat_db_exists():
            return
        stats = self.db.get_statistik()
        self._card_gesamt.set_value(stats.get("artikel_gesamt", 0))
        self._card_niedrig.set_value(stats.get("niedrig_bestand", 0))
        self._card_leer.set_value(stats.get("leer", 0))
        self._card_heute.set_value(stats.get("buchungen_heute", 0))

        niedrig = self.db.get_niedrig_bestand()
        self._tbl_niedrig.setRowCount(len(niedrig))
        crit_color = QColor("#FFCCBC")
        warn_color = QColor("#FFF3CD")
        for r, a in enumerate(niedrig):
            menge = int(a.get("menge", 0))
            min_m = int(a.get("min_menge", 0))
            vals = [
                a.get("bezeichnung", ""),
                a.get("kategorie", ""),
                f"{menge} {a.get('einheit', '')}".strip(),
                str(min_m),
                a.get("lagerort", ""),
            ]
            color = crit_color if menge == 0 else warn_color
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setBackground(color)
                self._tbl_niedrig.setItem(r, c, it)

    def _set_min5(self):
        n = self.db.set_default_min_menge(5)
        QMessageBox.information(self, "Mindestbestand", f"Mindestbestand auf 5 gesetzt für {n} Artikel.")
        self._refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
