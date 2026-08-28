from __future__ import annotations

from typing import Callable
import webbrowser

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CliAgentGuideDialog(QDialog):
    """Information and setup guide for terminal CLI AI agents."""

    def __init__(
        self,
        parent: QWidget | None = None,
        on_reload_providers: Callable[[], int] | None = None,
    ):
        super().__init__(parent)
        self.on_reload_providers = on_reload_providers
        self.setWindowTitle("CLI AI Agents: Advantages & Setup Guide")
        self.resize(680, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("🚀 Why Use a Terminal CLI AI Agent?")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        intro = QLabel(
            "Terminal CLI AI agents run locally in your environment to automate PDF question extraction, "
            "OCR for scanned exams, and batch processing without manual copy-pasting."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        group_adv = QGroupBox("Key Advantages of CLI Agents over Web Chats")
        adv_layout = QVBoxLayout(group_adv)
        adv_text = QLabel(
            "• <b>Full Automation:</b> Inspects the PDF directly on disk and saves <code>questions.md</code> automatically.<br>"
            "• <b>Super Batch Mode:</b> Processes dozens of exams concurrently in parallel with zero manual clicks.<br>"
            "• <b>No File Size or Token Limits:</b> Inspects multi-page exams directly without web upload restrictions.<br>"
            "• <b>Privacy & Speed:</b> Executes directly on your machine within your local workspace."
        )
        adv_text.setWordWrap(True)
        adv_layout.addWidget(adv_text)
        layout.addWidget(group_adv)

        group_install = QGroupBox("How to Install a CLI Agent")
        inst_layout = QVBoxLayout(group_install)
        inst_text = QLabel(
            "Install any supported CLI tool and ensure it is available in your system <b>PATH</b>:<br><br>"
            "• <b>Claude Code CLI:</b> <code>npm install -g @anthropic-ai/claude-code</code><br>"
            "• <b>Antigravity CLI:</b> <code>agy</code><br>"
            "• <b>Freebuff CLI:</b> <code>freebuff</code><br>"
            "• <b>Ollama (Offline/Local models):</b> <code>ollama</code> (https://ollama.com)<br>"
            "• <b>Gemini / LLM CLIs:</b> <code>pip install google-genai</code> or <code>pip install llm</code>"
        )
        inst_text.setWordWrap(True)
        inst_layout.addWidget(inst_text)
        layout.addWidget(group_install)

        btn_row = QHBoxLayout()
        btn_search = QPushButton("🔍 Search Google for CLI AI Agents")
        btn_search.setToolTip("Open browser to search for CLI AI agent guides.")
        btn_search.clicked.connect(
            lambda: webbrowser.open(
                "https://www.google.com/search?q=install+terminal+ai+cli+agents+claude+code+gemini+ollama"
            )
        )
        btn_row.addWidget(btn_search)

        if self.on_reload_providers:
            btn_reload = QPushButton("🔄 Reload Detected AI Providers")
            btn_reload.setToolTip("Scan system PATH for newly installed CLI AI tools.")
            btn_reload.clicked.connect(self._handle_reload)
            btn_row.addWidget(btn_reload)

        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _handle_reload(self) -> None:
        if self.on_reload_providers:
            count = self.on_reload_providers()
            QMessageBox.information(
                self,
                "Providers Reloaded",
                f"Scanned system PATH. {count} local CLI AI tool(s) detected.",
            )

