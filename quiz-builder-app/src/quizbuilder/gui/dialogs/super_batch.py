from __future__ import annotations

import logging
from pathlib import Path
import threading
from typing import Any, Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config import Config
from ...exporter import build_standalone_quiz
from ...super_batch import (
    SuperBatchItem,
    SuperBatchPlan,
    build_plan,
    classify_plan_item,
    default_decision,
    process_plan,
)
from ..workers import Worker

LOGGER = logging.getLogger(__name__)


class SuperBatchProgressDialog(QDialog):
    """Live progress monitor dialog for running Super Batch jobs."""

    def __init__(
        self,
        parent: QWidget | None,
        exec_plan: SuperBatchPlan,
        provider_label: str,
        cancel_event: threading.Event,
    ):
        super().__init__(parent)
        self.exec_plan = exec_plan
        self.cancel_event = cancel_event

        self.setWindowTitle("Super Batch in Progress")
        self.resize(800, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.header_label = QLabel(
            f"<b>Running Super Batch:</b> {len(exec_plan.items)} exam(s) with {provider_label}"
        )
        layout.addWidget(self.header_label)

        self.p_bar = QProgressBar()
        self.p_bar.setRange(0, len(exec_plan.items))
        self.p_bar.setValue(0)
        self.p_bar.setFormat("%v / %m exams completed (%p%)")
        layout.addWidget(self.p_bar)

        self.p_table = QTableWidget(len(exec_plan.items), 4, self)
        self.p_table.setHorizontalHeaderLabels(["Exam", "Type", "Status", "Details"])
        self.p_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.p_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.p_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.p_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.item_row_map: dict[int, int] = {}
        for r_idx, itm in enumerate(exec_plan.items):
            self.item_row_map[id(itm)] = r_idx
            self.p_table.setItem(r_idx, 0, QTableWidgetItem(itm.overview.name))
            self.p_table.setItem(r_idx, 1, QTableWidgetItem("Digital" if itm.overview.is_digital else "Scanned"))
            self.p_table.setItem(r_idx, 2, QTableWidgetItem("⏳ Pending"))
            self.p_table.setItem(r_idx, 3, QTableWidgetItem(""))
        layout.addWidget(self.p_table)

        self.cancel_btn = QPushButton("Cancel Super Batch")
        layout.addWidget(self.cancel_btn)
        self.cancel_btn.clicked.connect(self._handle_cancel)

        self.completed_count = 0

    def _handle_cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling… waiting for active jobs to terminate")

    def update_item_progress(self, updated_item: SuperBatchItem) -> None:
        r_idx = self.item_row_map.get(id(updated_item))
        if r_idx is not None:
            status_icons = {
                "pending": "⏳ Pending",
                "classifying": "🔍 Classifying",
                "extracting": "⚙️ Extracting",
                "generating": "🤖 Generating",
                "saved": "✅ Saved",
                "failed": "❌ Failed",
                "cancelled": "🚫 Cancelled",
            }
            status_text = status_icons.get(updated_item.status, updated_item.status)
            self.p_table.setItem(r_idx, 2, QTableWidgetItem(status_text))
            detail = updated_item.error or (
                f"Saved questions.md in {updated_item.overview.workspace.name}"
                if updated_item.status == "saved"
                else ""
            )
            self.p_table.setItem(r_idx, 3, QTableWidgetItem(detail))
            if updated_item.status in {"saved", "failed", "cancelled"}:
                self.completed_count += 1
                self.p_bar.setValue(self.completed_count)


class SuperBatchSummaryDialog(QDialog):
    """Summary dialog shown after Super Batch completes."""

    def __init__(
        self,
        parent: QWidget | None,
        results: list[Any],
        config: Config,
        on_retry_failed: Callable[[list[SuperBatchItem]], None] | None = None,
    ):
        super().__init__(parent)
        self.results = results
        self.config = config
        self.on_retry_failed = on_retry_failed

        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        self.setWindowTitle("Super Batch Results")
        self.resize(750, 480)
        s_layout = QVBoxLayout(self)

        headline = QLabel(
            f"<h3>Super Batch Complete</h3>"
            f"<p><b>{len(succeeded)}</b> succeeded, <b>{len(failed)}</b> failed out of <b>{len(results)}</b> total exams.</p>"
        )
        s_layout.addWidget(headline)

        res_table = QTableWidget(len(results), 3, self)
        res_table.setHorizontalHeaderLabels(["Exam", "Result", "Output / Error Details"])
        res_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        res_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        res_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for idx, res in enumerate(results):
            res_table.setItem(idx, 0, QTableWidgetItem(res.item.overview.name))
            res_table.setItem(idx, 1, QTableWidgetItem("✅ Succeeded" if res.success else "❌ Failed"))
            detail_text = str(res.output) if res.success else str(res.error)
            res_table.setItem(idx, 2, QTableWidgetItem(detail_text))
        s_layout.addWidget(res_table)

        btn_box = QHBoxLayout()
        if succeeded:
            build_html_btn = QPushButton("⚡ Build HTML Quizzes for Successful Items")
            btn_box.addWidget(build_html_btn)

            def build_htmls():
                build_html_btn.setEnabled(False)
                build_html_btn.setText("Building HTML quizzes...")
                built_count = 0
                errors = []
                for res in succeeded:
                    try:
                        build_standalone_quiz(res.item.overview.workspace, self.config.scripts_root)
                        built_count += 1
                    except Exception as e:
                        errors.append(f"{res.item.overview.name}: {e}")
                build_html_btn.setText(f"Built {built_count} HTML Quiz(zes)")
                if errors:
                    QMessageBox.warning(
                        self,
                        "HTML Quiz Build Warning",
                        f"Built {built_count} quizzes, but encountered errors:\n" + "\n".join(errors),
                    )
                else:
                    QMessageBox.information(
                        self,
                        "HTML Quizzes Built",
                        f"Successfully built {built_count} standalone HTML quiz(zes)!",
                    )

            build_html_btn.clicked.connect(build_htmls)

        if failed and self.on_retry_failed:
            retry_btn = QPushButton("🔄 Retry Failed Items Only")
            btn_box.addWidget(retry_btn)

            def retry_failed():
                self.accept()
                failed_items = [r.item for r in failed]
                for it in failed_items:
                    it.status = "pending"
                    it.error = None
                self.on_retry_failed(failed_items)

            retry_btn.clicked.connect(retry_failed)

        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        s_layout.addLayout(btn_box)


class SuperBatchDialog(QDialog):
    """Main setup and review dialog for Super Batch runs."""

    def __init__(
        self,
        parent: QWidget | None,
        root: Path,
        config: Config,
        local_providers: list[tuple[Any, str]],
        custom_items: list[SuperBatchItem] | None = None,
        discard_rule: str = "std",
    ):
        super().__init__(parent)
        self.root = root
        self.config = config
        self.local_providers = local_providers
        self.discard_rule = discard_rule

        if custom_items is not None:
            self.plan = SuperBatchPlan(root=self.root, items=tuple(custom_items))
        else:
            self.plan = build_plan(self.root)

        for item in self.plan.items:
            classify_plan_item(item)
            if item.decision is None:
                item.decision = default_decision(item)

        self.setWindowTitle("Review Super Batch Exams")
        self.resize(1050, 680)

        self.rows_data: list[tuple[SuperBatchItem, QCheckBox, QComboBox, QComboBox, QCheckBox, QLineEdit]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Review discovered exams below. Configure settings, uncheck unwanted items, and click <b>Start Super Batch</b>.")
        )

        form = QFormLayout()
        self.provider_combo = QComboBox()
        for provider_option, command_option in self.local_providers:
            self.provider_combo.addItem(
                f"{provider_option.label} ({command_option})",
                (provider_option, command_option),
            )
        form.addRow("Local CLI AI:", self.provider_combo)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(max(1, self.config.super_batch_workers))
        form.addRow("Parallel workers:", self.workers_spin)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Two phases (overview + questions)", "two_phase")
        self.mode_combo.addItem("Single invocation (all-in-one)", "single_invocation")
        self.mode_combo.setCurrentIndex(0 if self.config.super_batch_ai_mode == "two_phase" else 1)
        form.addRow("AI mode:", self.mode_combo)

        rule = self.discard_rule or self.config.default_discard_pages or "std"
        self.clean_check = QCheckBox(f"Apply digital PDF page cleaning (rule: '{rule}')")
        self.clean_check.setChecked(True)
        self.clean_check.setToolTip(f"Cleans digital PDFs using the '{rule}' rule before question extraction.")
        form.addRow("PDF cleanup:", self.clean_check)

        self.context_mode = QComboBox()
        self.context_mode.addItem("AI OCR from PDF path (recommended)", "path")
        self.context_mode.addItem("AI OCR with local text hint", "extracted")
        self.context_mode.setCurrentIndex(0)
        self.context_mode.setToolTip("Scanned PDFs always go through the AI for OCR. Choose whether to provide the PDF path alone or add locally extracted text as a hint.")
        form.addRow("Scanned PDF context:", self.context_mode)
        layout.addLayout(form)

        # Bulk Actions Toolbar
        btn_bar = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_deselect_all = QPushButton("Deselect All")
        btn_set_zero_test = QPushButton("Set Digital to Zero-Test")
        btn_auto_match = QPushButton("Auto-Match Keys")
        btn_bar.addWidget(btn_select_all)
        btn_bar.addWidget(btn_deselect_all)
        btn_bar.addWidget(btn_set_zero_test)
        btn_bar.addWidget(btn_auto_match)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Review Table
        table = QTableWidget(len(self.plan.items), 8, self)
        table.setHorizontalHeaderLabels([
            "Include", "Exam Name", "Type", "Metadata", "Answer Key", "Decision", "Overwrite?", "Dedicated Instructions"
        ])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self.rows_data = []
        for row_idx, item in enumerate(self.plan.items):
            # 0: Include checkbox
            include_box = QCheckBox()
            include_box.setChecked(True)
            include_widget = QWidget()
            include_layout = QHBoxLayout(include_widget)
            include_layout.addWidget(include_box)
            include_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            include_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(row_idx, 0, include_widget)

            # 1: Exam Name
            name_item = QTableWidgetItem(item.overview.name)
            name_item.setToolTip(f"PDF: {item.overview.pdf}\nWorkspace: {item.overview.workspace}")
            table.setItem(row_idx, 1, name_item)

            # 2: Type
            type_str = "📄 Digital" if item.overview.is_digital else "📷 Scanned"
            table.setItem(row_idx, 2, QTableWidgetItem(type_str))

            # 3: Metadata
            info_parts = []
            if item.overview.test_number:
                info_parts.append(f"Test {item.overview.test_number}")
            if item.overview.year:
                info_parts.append(item.overview.year)
            if item.overview.variant:
                info_parts.append(f"Moed {item.overview.variant.upper()}")
            table.setItem(row_idx, 3, QTableWidgetItem(" | ".join(info_parts) or "-"))

            # 4: Answer Key
            key_combo = QComboBox()
            key_combo.addItem("No answer key", None)
            for candidate in item.answer_keys:
                label = candidate.path.name
                if candidate.answers:
                    label += f" ({len(candidate.answers)} ans)"
                key_combo.addItem(label, candidate.path)

            if item.selected_answer_key:
                for i in range(key_combo.count()):
                    if key_combo.itemData(i) == item.selected_answer_key:
                        key_combo.setCurrentIndex(i)
                        break
            elif item.answer_keys and item.answer_keys[0].score >= 0:
                key_combo.setCurrentIndex(1)
                item.selected_answer_key = item.answer_keys[0].path
            table.setCellWidget(row_idx, 4, key_combo)

            # 5: Decision
            decision_combo = QComboBox()
            decision_combo.addItem("Use answer key", "use_answer_key")
            decision_combo.addItem("Generate only (unanswered)", "generate_only")
            decision_combo.addItem("Zero test (all A)", "zero_test")
            if key_combo.currentIndex() > 0 or item.selected_answer_key:
                decision_combo.setCurrentIndex(0)
            elif item.overview.is_digital:
                decision_combo.setCurrentIndex(2)
            else:
                decision_combo.setCurrentIndex(1)
            table.setCellWidget(row_idx, 5, decision_combo)

            def make_on_key_changed(d_cb=decision_combo, itm=item):
                def on_key_changed(idx: int):
                    if idx > 0:
                        d_cb.setCurrentIndex(0)
                    else:
                        d_cb.setCurrentIndex(2 if itm.overview.is_digital else 1)
                return on_key_changed

            key_combo.currentIndexChanged.connect(make_on_key_changed(decision_combo, item))

            # 6: Overwrite
            exists = (item.overview.workspace / "questions.md").exists()
            overwrite_box = QCheckBox("⚠️ Exists" if exists else "New")
            overwrite_box.setChecked(not exists)
            if exists:
                overwrite_box.setToolTip(f"questions.md already exists in {item.overview.workspace}. Check to overwrite.")
            overwrite_widget = QWidget()
            overwrite_layout = QHBoxLayout(overwrite_widget)
            overwrite_layout.addWidget(overwrite_box)
            overwrite_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overwrite_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(row_idx, 6, overwrite_widget)

            # 7: Instructions
            instructions = QLineEdit()
            instructions.setPlaceholderText("Optional dedicated prompt instructions...")
            table.setCellWidget(row_idx, 7, instructions)

            self.rows_data.append((item, include_box, key_combo, decision_combo, overwrite_box, instructions))

        # Connect bulk actions
        btn_select_all.clicked.connect(lambda: [inc.setChecked(True) for _, inc, _, _, _, _ in self.rows_data])
        btn_deselect_all.clicked.connect(lambda: [inc.setChecked(False) for _, inc, _, _, _, _ in self.rows_data])

        def set_all_zero_test():
            for itm, _, k_combo, dec, _, _ in self.rows_data:
                if itm.overview.is_digital:
                    k_combo.setCurrentIndex(0)
                    dec.setCurrentIndex(2)

        def auto_match_all():
            for itm, _, k_combo, dec_combo, _, _ in self.rows_data:
                if itm.answer_keys and itm.answer_keys[0].score >= 0:
                    k_combo.setCurrentIndex(1)
                    dec_combo.setCurrentIndex(0)

        btn_set_zero_test.clicked.connect(set_all_zero_test)
        btn_auto_match.clicked.connect(auto_match_all)

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Super Batch")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_items(self) -> list[SuperBatchItem]:
        selected_items = []
        for item, include_box, key_combo, decision_combo, overwrite_box, instructions in self.rows_data:
            if not include_box.isChecked():
                continue
            item.selected_answer_key = key_combo.currentData()
            item.decision = decision_combo.currentData()
            item.overwrite = overwrite_box.isChecked()
            item.dedicated_instructions = instructions.text().strip()
            if item.decision == "use_answer_key" and not item.selected_answer_key and not item.overview.is_digital:
                item.decision = "generate_only"
            selected_items.append(item)
        return selected_items

    def get_execution_params(self) -> dict[str, Any]:
        provider, command = self.provider_combo.currentData()
        rule = self.discard_rule or self.config.default_discard_pages or "std"
        return {
            "provider": provider,
            "command": command,
            "workers": self.workers_spin.value(),
            "ai_mode": self.mode_combo.currentData(),
            "context_mode": self.context_mode.currentData(),
            "discard_pages": rule if self.clean_check.isChecked() else "",
            "clean_digital": self.clean_check.isChecked(),
        }

