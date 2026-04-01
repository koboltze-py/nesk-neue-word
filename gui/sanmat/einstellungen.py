"""
Sanitätsmaterial – Info / Einstellungen
Datenbankinfo anzeigen, Artikel zurücksetzen.
"""

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt

from config import SANMAT_DB_PATH


class EinstellungenView(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        lbl_title = QLabel("Sanmat – Info & Einstellungen")
        lbl_title.setObjectName("page_title")
        lbl_sub = QLabel("Datenbankübersicht und Initialdaten-Verwaltung")
        lbl_sub.setObjectName("page_subtitle")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # --- Datenbankinfo ---
        grp_db = QGroupBox("Datenbank-Information")
        db_layout = QVBoxLayout(grp_db)
        db_layout.setContentsMargins(16, 16, 16, 16)
        db_layout.setSpacing(8)
        self._lbl_db_info = QLabel("...")
        self._lbl_db_info.setWordWrap(True)
        self._lbl_db_info.setStyleSheet("font-size:12px;")
        db_layout.addWidget(self._lbl_db_info)
        btn_info = QPushButton("Info aktualisieren")
        btn_info.setObjectName("btn_secondary")
        btn_info.setMaximumWidth(180)
        btn_info.clicked.connect(self._update_db_info)
        db_layout.addWidget(btn_info)
        layout.addWidget(grp_db)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # --- Initialartikell ---
        grp_init = QGroupBox("Initialdaten")
        init_layout = QVBoxLayout(grp_init)
        init_layout.setContentsMargins(16, 16, 16, 16)
        init_layout.setSpacing(8)
        lbl_init = QLabel(
            "Fügt die vordefinierten meetB-Artikel ein, die noch nicht in der Datenbank vorhanden sind.\n"
            "Bereits vorhandene Artikel werden nicht verändert."
        )
        lbl_init.setWordWrap(True)
        init_layout.addWidget(lbl_init)
        btn_import = QPushButton("Fehlende Initialartikel einfügen")
        btn_import.setObjectName("btn_secondary")
        btn_import.setMaximumWidth(280)
        btn_import.clicked.connect(self._import_initial)
        init_layout.addWidget(btn_import)
        layout.addWidget(grp_init)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # --- Backup-Hinweis ---
        grp_backup = QGroupBox("Backup")
        bk_layout = QVBoxLayout(grp_backup)
        bk_layout.setContentsMargins(16, 16, 16, 16)
        lbl_bk = QLabel(
            "Die Sanmat-Datenbank (sanmat.db) wird beim Start von Nesk3 automatisch\n"
            "zusammen mit allen anderen Datenbanken gesichert.\n\n"
            "Manuelle Backups können über den Backup-Bereich in der Nesk3-Sidebar\n"
            "erstellt werden."
        )
        lbl_bk.setWordWrap(True)
        lbl_bk.setStyleSheet("color:#555; font-size:12px;")
        bk_layout.addWidget(lbl_bk)
        layout.addWidget(grp_backup)

        layout.addStretch()

    def _update_db_info(self):
        if not self.db.sanmat_db_exists():
            self._lbl_db_info.setText("Datenbank nicht gefunden.")
            return
        try:
            size_kb = os.path.getsize(SANMAT_DB_PATH) / 1024
        except Exception:
            size_kb = 0.0
        stats = self.db.get_statistik()
        self._lbl_db_info.setText(
            f"Pfad: {SANMAT_DB_PATH}\n"
            f"Größe: {size_kb:.1f} KB\n"
            f"Aktive Artikel: {stats.get('artikel_gesamt', 0)}\n"
            f"Buchungen heute: {stats.get('buchungen_heute', 0)}\n"
            f"Artikel mit Niedrigbestand: {stats.get('niedrig_bestand', 0)}\n"
            f"Artikel mit Bestand = 0: {stats.get('leer', 0)}"
        )

    def _import_initial(self):
        n = self.db.upsert_initial_artikel()
        if n == 0:
            QMessageBox.information(self, "Import", "Alle Initialartikel sind bereits vorhanden.")
        else:
            QMessageBox.information(self, "Import", f"{n} neue Artikel wurden eingefügt.")

    def showEvent(self, event):
        super().showEvent(event)
        self._update_db_info()
