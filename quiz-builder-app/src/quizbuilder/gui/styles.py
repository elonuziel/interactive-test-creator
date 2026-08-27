"""Application-wide Qt stylesheets for the quiz builder GUI."""

_COMMON = """
QWidget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 13px; }
QPushButton { border-radius: 6px; padding: 7px 14px; font-weight: 500; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { border-radius: 6px; padding: 6px 10px; }
QGroupBox { font-weight: 600; border-radius: 8px; margin-top: 12px; padding: 14px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
QListWidget::item { padding: 7px 10px; border-radius: 5px; margin-bottom: 2px; }
"""

LITE_STYLESHEET = _COMMON + """
QWidget { color: #1e293b; background: #f8fafc; }
QGroupBox, QTabWidget::pane, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { background: #ffffff; border: 1px solid #cbd5e1; }
QPushButton { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
QPushButton:hover { background: #e2e8f0; }
QTabBar::tab { background: #f1f5f9; color: #64748b; padding: 10px 22px; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; }
QListWidget::item:selected { background: #e0e7ff; color: #1e1b4b; }
"""

DARK_STYLESHEET = _COMMON + """
QWidget { color: #e2e8f0; background: #0f172a; }
QGroupBox, QTabWidget::pane, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { background: #1e293b; border: 1px solid #475569; color: #e2e8f0; }
QPushButton { background: #334155; color: #f8fafc; border: 1px solid #64748b; }
QPushButton:hover { background: #475569; }
QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 10px 22px; }
QTabBar::tab:selected { background: #334155; color: #93c5fd; }
QListWidget::item:selected { background: #3730a3; color: #eef2ff; }
QLabel { color: #e2e8f0; }
"""
