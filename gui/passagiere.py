"""
Passagiere Haupt-Widget
Kombiniert Passagieranfragen und Beschwerden als Tabs.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtGui import QFont


class PassagiereWidget(QWidget):
    """Kombiniertes Widget: Passagieranfragen + Beschwerden als Tabs."""

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
                min-width: 200px;
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

        from gui.passagieranfragen import PassagieranfragenWidget
        from gui.beschwerden import BeschwerdenWidget

        self._passagieranfragen_tab = PassagieranfragenWidget()
        self._beschwerden_tab       = BeschwerdenWidget()

        self._tabs.addTab(self._passagieranfragen_tab, "✉️  Passagieranfragen")
        self._tabs.addTab(self._beschwerden_tab,       "📣  Beschwerden")

        layout.addWidget(self._tabs)

    def refresh(self):
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._passagieranfragen_tab.refresh()
        else:
            self._beschwerden_tab._load()
