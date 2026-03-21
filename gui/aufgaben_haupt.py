"""
Aufgaben Haupt-Widget
Kombiniert Aufgaben Tag und Aufgaben Nacht als Tabs.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtGui import QFont


class AufgabenHauptWidget(QWidget):
    """Kombiniertes Widget: Tab Aufgaben Tag + Tab Aufgaben Nacht."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setFont(QFont("Segoe UI", 12))
        self._tabs.setStyleSheet("""
            QTabBar::tab {
                min-width: 180px;
                padding: 10px 20px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1565a8;
                font-weight: bold;
                border-bottom: 2px solid #1565a8;
            }
        """)

        from gui.aufgaben_tag import AufgabenTagWidget
        from gui.aufgaben import AufgabenWidget

        self._tag_tab   = AufgabenTagWidget()
        self._nacht_tab = AufgabenWidget()

        self._tabs.addTab(self._tag_tab,   "☀️  Aufgaben Tag")
        self._tabs.addTab(self._nacht_tab, "🌙  Aufgaben Nacht")

        layout.addWidget(self._tabs)

    def refresh(self):
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._tag_tab.refresh()
        else:
            self._nacht_tab.refresh()
