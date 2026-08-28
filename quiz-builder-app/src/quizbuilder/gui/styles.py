"""Application-wide Qt stylesheets for the quiz builder GUI."""

_COMMON = """
QWidget { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 13px; }
QPushButton { border-radius: 6px; padding: 7px 14px; font-weight: 500; }
QPushButton#primary { border-radius: 6px; padding: 7px 20px; font-weight: 700; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { border-radius: 6px; padding: 6px 10px; }
QGroupBox { font-weight: 600; border-radius: 8px; margin-top: 12px; padding: 14px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
QListWidget::item { padding: 7px 10px; border-radius: 5px; margin-bottom: 2px; }
QProgressBar { border-radius: 4px; border: none; }
QProgressBar::chunk { border-radius: 4px; }
"""

LITE_STYLESHEET = _COMMON + """
QWidget { color: #1e293b; background: #f8fafc; }
QGroupBox, QTabWidget::pane, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { background: #ffffff; border: 1px solid #cbd5e1; }
QFrame#topBar, QFrame#statusBar { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }
QLabel#badge { background: #e2e8f0; color: #1e293b; font-weight: bold; border-radius: 4px; padding: 4px; }
QPushButton { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
QPushButton:hover { background: #e2e8f0; }
QPushButton:disabled { background: #f8fafc; color: #94a3b8; border-color: #e2e8f0; }
QPushButton#primary { background: #2563eb; color: #ffffff; border: 1px solid #1d4ed8; }
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:disabled { background: #bfdbfe; color: #f8fafc; border-color: #bfdbfe; }
QTabBar::tab { background: #f1f5f9; color: #64748b; padding: 10px 22px; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; font-weight: 600; }
QListWidget::item:selected { background: #e0e7ff; color: #1e1b4b; }
QFrame#draggablePdf { background: #eff6ff; border: 2px dashed #93c5fd; border-radius: 8px; }
QFrame#draggablePdf:hover { background: #dbeafe; border-color: #3b82f6; }
QProgressBar { background: #e2e8f0; }
QProgressBar::chunk { background: #2563eb; }
"""

DARK_STYLESHEET = _COMMON + """
QWidget { color: #e2e8f0; background: #0f172a; }
QGroupBox, QTabWidget::pane, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget { background: #1e293b; border: 1px solid #475569; color: #e2e8f0; }
QFrame#topBar, QFrame#statusBar { background: #1e293b; border: 1px solid #334155; border-radius: 8px; }
QLabel#badge { background: #334155; color: #e2e8f0; font-weight: bold; border-radius: 4px; padding: 4px; }
QPushButton { background: #334155; color: #f8fafc; border: 1px solid #64748b; }
QPushButton:hover { background: #475569; }
QPushButton:disabled { background: #1e293b; color: #64748b; border-color: #334155; }
QPushButton#primary { background: #3b82f6; color: #ffffff; border: 1px solid #2563eb; }
QPushButton#primary:hover { background: #2563eb; }
QPushButton#primary:disabled { background: #1d4ed8; color: #bfdbfe; border-color: #1d4ed8; }
QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 10px 22px; }
QTabBar::tab:selected { background: #334155; color: #93c5fd; font-weight: 600; }
QListWidget::item:selected { background: #3730a3; color: #eef2ff; }
QFrame#draggablePdf { background: #1e293b; border: 2px dashed #3b82f6; border-radius: 8px; }
QFrame#draggablePdf:hover { background: #1e3a8a; border-color: #60a5fa; }
QLabel { color: #e2e8f0; }
QProgressBar { background: #334155; }
QProgressBar::chunk { background: #3b82f6; }
"""
