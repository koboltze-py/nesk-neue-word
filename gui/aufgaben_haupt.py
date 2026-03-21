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
                font-family: 'Segoe UI';
                color: #666;
                background: transparent;
                border-bottom: 3px solid transparent;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                color: #1565a8;
                font-weight: bold;
                border-bottom: 3px solid #1565a8;
            }
            QTabBar::tab:hover:!selected {
                color: #1565a8;
                border-bottom: 3px solid #ccddf5;
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
