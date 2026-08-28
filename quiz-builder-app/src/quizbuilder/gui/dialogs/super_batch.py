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
        initially_checked_names: set[str] | None = None,
    ):
        super().__init__(parent)
        self.root = root
        self.config = config
        self.local_providers = local_providers
        self.discard_rule = discard_rule
        self.initially_checked_names = initially_checked_names

        if custom_items is not None:
            self.plan = SuperBatchPlan(root=self.root, items=tuple(custom_items))
        else:
            self.plan = build_plan(self.root)

        for item in self.plan.items:
            classify_plan_item(item)
            if item.decision is None:
                item.decision = default_decision(item)

        self.setWindowTitle("Review Super Batch Exams")
        self.resize(1150, 720)
        self.setMinimumSize(850, 520)

        self.rows_data: list[dict[str, Any]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("Review discovered exams below. Configure settings, uncheck or set <b>Skip</b> for unwanted items, and click <b>Start Super Batch</b>.")
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
        btn_deselect_all = QPushButton("Deselect / Skip All")
        btn_set_zero_test = QPushButton("Set Digital to Zero-Test")
        btn_auto_match = QPushButton("Auto-Match Keys")
        self.selected_count_label = QLabel()
        self.selected_count_label.setStyleSheet("font-weight: bold; color: #38bdf8; margin-left: 10px;")

        btn_bar.addWidget(btn_select_all)
        btn_bar.addWidget(btn_deselect_all)
        btn_bar.addWidget(btn_set_zero_test)
        btn_bar.addWidget(btn_auto_match)
        btn_bar.addWidget(self.selected_count_label)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Review Table
        self.table = QTableWidget(len(self.plan.items), 8, self)
        self.table.setHorizontalHeaderLabels([
            "Include", "Exam Name", "Type", "Metadata", "Answer Key", "Decision", "Overwrite?", "Dedicated Instructions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 65)
        self.table.setColumnWidth(1, 200)

        self.rows_data = []
        for row_idx, item in enumerate(self.plan.items):
            init_checked = True
            if self.initially_checked_names is not None:
                init_checked = (item.overview.name in self.initially_checked_names)

            # 0: Include checkbox
            include_box = QCheckBox()
            include_box.setChecked(init_checked)
            include_box.setToolTip("Uncheck to skip this exam")
            include_widget = QWidget()
            include_layout = QHBoxLayout(include_widget)
            include_layout.addWidget(include_box)
            include_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            include_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row_idx, 0, include_widget)

            # 1: Exam Name
            name_item = QTableWidgetItem(item.overview.name)
            name_item.setToolTip(f"PDF: {item.overview.pdf}\nWorkspace: {item.overview.workspace}")
            self.table.setItem(row_idx, 1, name_item)

            # 2: Type (Use clear text badges without emojis that render as missing glyph boxes on Linux)
            type_str = "Digital" if item.overview.is_digital else "Scanned"
            type_item = QTableWidgetItem(type_str)
            type_item.setToolTip("Digital = text PDF | Scanned = scanned/image PDF")
            self.table.setItem(row_idx, 2, type_item)

            # 3: Metadata
            info_parts = []
            if item.overview.test_number:
                info_parts.append(f"Test {item.overview.test_number}")
            if item.overview.year:
                info_parts.append(item.overview.year)
            if item.overview.variant:
                info_parts.append(f"Moed {item.overview.variant.upper()}")
            meta_item = QTableWidgetItem(" | ".join(info_parts) or "-")
            self.table.setItem(row_idx, 3, meta_item)

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
            self.table.setCellWidget(row_idx, 4, key_combo)

            # 5: Decision
            decision_combo = QComboBox()
            decision_combo.addItem("Use answer key", "use_answer_key")
            decision_combo.addItem("Generate only (unanswered)", "generate_only")
            decision_combo.addItem("Zero test (all A)", "zero_test")
            decision_combo.addItem("🚫 Skip (Do not run)", "skip")

            if not init_checked:
                decision_combo.setCurrentIndex(3)
            elif key_combo.currentIndex() > 0 or item.selected_answer_key:
                decision_combo.setCurrentIndex(0)
            elif item.overview.is_digital:
                decision_combo.setCurrentIndex(2)
            else:
                decision_combo.setCurrentIndex(1)
            self.table.setCellWidget(row_idx, 5, decision_combo)

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
            self.table.setCellWidget(row_idx, 6, overwrite_widget)

            # 7: Instructions
            instructions = QLineEdit()
            instructions.setPlaceholderText("Optional dedicated prompt instructions...")
            self.table.setCellWidget(row_idx, 7, instructions)

            row_entry = {
                "item": item,
                "include_box": include_box,
                "key_combo": key_combo,
                "decision_combo": decision_combo,
                "overwrite_box": overwrite_box,
                "instructions": instructions,
                "row_idx": row_idx,
            }
            self.rows_data.append(row_entry)

            # Wire signals for row
            def _bind_row_signals(entry=row_entry, itm=item):
                inc_b = entry["include_box"]
                dec_c = entry["decision_combo"]
                k_c = entry["key_combo"]

                def on_key_changed(idx: int):
                    if dec_c.currentData() == "skip":
                        return
                    if idx > 0:
                        dec_c.setCurrentIndex(0)
                    else:
                        dec_c.setCurrentIndex(2 if itm.overview.is_digital else 1)

                def on_decision_changed(idx: int):
                    is_skip = (dec_c.itemData(idx) == "skip")
                    inc_b.blockSignals(True)
                    inc_b.setChecked(not is_skip)
                    inc_b.blockSignals(False)
                    self._update_row_state(entry)
                    self._update_selected_count()

                def on_include_toggled(checked: bool):
                    dec_c.blockSignals(True)
                    if not checked:
                        dec_c.setCurrentIndex(3)  # Skip
                    else:
                        if k_c.currentIndex() > 0 or itm.selected_answer_key:
                            dec_c.setCurrentIndex(0)
                        elif itm.overview.is_digital:
                            dec_c.setCurrentIndex(2)
                        else:
                            dec_c.setCurrentIndex(1)
                    dec_c.blockSignals(False)
                    self._update_row_state(entry)
                    self._update_selected_count()

                k_c.currentIndexChanged.connect(on_key_changed)
                dec_c.currentIndexChanged.connect(on_decision_changed)
                inc_b.toggled.connect(on_include_toggled)

            _bind_row_signals()
            self._update_row_state(row_entry)

        # Connect bulk actions
        def select_all():
            for entry in self.rows_data:
                entry["include_box"].blockSignals(True)
                entry["include_box"].setChecked(True)
                entry["include_box"].blockSignals(False)
                entry["decision_combo"].blockSignals(True)
                itm = entry["item"]
                if entry["key_combo"].currentIndex() > 0 or itm.selected_answer_key:
                    entry["decision_combo"].setCurrentIndex(0)
                elif itm.overview.is_digital:
                    entry["decision_combo"].setCurrentIndex(2)
                else:
                    entry["decision_combo"].setCurrentIndex(1)
                entry["decision_combo"].blockSignals(False)
                self._update_row_state(entry)
            self._update_selected_count()

        def deselect_all():
            for entry in self.rows_data:
                entry["include_box"].blockSignals(True)
                entry["include_box"].setChecked(False)
                entry["include_box"].blockSignals(False)
                entry["decision_combo"].blockSignals(True)
                entry["decision_combo"].setCurrentIndex(3)  # Skip
                entry["decision_combo"].blockSignals(False)
                self._update_row_state(entry)
            self._update_selected_count()

        def set_all_zero_test():
            for entry in self.rows_data:
                if entry["include_box"].isChecked() and entry["item"].overview.is_digital:
                    entry["key_combo"].setCurrentIndex(0)
                    entry["decision_combo"].setCurrentIndex(2)
            self._update_selected_count()

        def auto_match_all():
            for entry in self.rows_data:
                itm = entry["item"]
                if entry["include_box"].isChecked() and itm.answer_keys and itm.answer_keys[0].score >= 0:
                    entry["key_combo"].setCurrentIndex(1)
                    entry["decision_combo"].setCurrentIndex(0)
            self._update_selected_count()

        btn_select_all.clicked.connect(select_all)
        btn_deselect_all.clicked.connect(deselect_all)
        btn_set_zero_test.clicked.connect(set_all_zero_test)
        btn_auto_match.clicked.connect(auto_match_all)

        layout.addWidget(self.table)

        options_bottom_row = QHBoxLayout()
        self.auto_build_html_check = QCheckBox("Automatically build standalone HTMLs and Central Hub (quiz_hub.html) upon completion")
        self.auto_build_html_check.setChecked(True)
        self.auto_build_html_check.setToolTip("Compile standalone quiz.html in each exam folder and generate quiz_hub.html in the root directory.")
        options_bottom_row.addWidget(self.auto_build_html_check)
        options_bottom_row.addStretch()
        layout.addLayout(options_bottom_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Super Batch")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_selected_count()
        QTimer.singleShot(0, lambda: self.table.horizontalScrollBar().setValue(0))

    def _update_row_state(self, entry: dict[str, Any]) -> None:
        included = entry["include_box"].isChecked() and entry["decision_combo"].currentData() != "skip"
        entry["key_combo"].setEnabled(included)
        entry["overwrite_box"].setEnabled(included)
        entry["instructions"].setEnabled(included)

        r = entry["row_idx"]
        for c in range(self.table.columnCount()):
            item = self.table.item(r, c)
            if item:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled if included else item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _update_selected_count(self) -> None:
        total = len(self.rows_data)
        selected = sum(1 for e in self.rows_data if e["include_box"].isChecked() and e["decision_combo"].currentData() != "skip")
        skipped = total - selected
        if skipped > 0:
            self.selected_count_label.setText(f"Selected: {selected} / {total} exams ({skipped} skipped)")
        else:
            self.selected_count_label.setText(f"Selected: {selected} / {total} exams (All included)")

    def get_selected_items(self) -> list[SuperBatchItem]:
        selected_items = []
        for entry in self.rows_data:
            if not entry["include_box"].isChecked() or entry["decision_combo"].currentData() == "skip":
                continue
            item = entry["item"]
            item.selected_answer_key = entry["key_combo"].currentData()
            item.decision = entry["decision_combo"].currentData()
            item.overwrite = entry["overwrite_box"].isChecked()
            item.dedicated_instructions = entry["instructions"].text().strip()
            if item.decision == "use_answer_key" and not item.selected_answer_key and not item.overview.is_digital:
                item.decision = "generate_only"
            selected_items.append(item)
        return selected_items

    def get_execution_plan(self) -> SuperBatchPlan:
        return SuperBatchPlan(root=self.root, items=tuple(self.get_selected_items()))

    def get_selected_provider(self) -> tuple[Any, str]:
        return self.provider_combo.currentData()

    def get_execution_params(self) -> dict[str, Any]:
        provider, command = self.provider_combo.currentData()
        rule = self.discard_rule or self.config.default_discard_pages or "std"
        auto_build = self.auto_build_html_check.isChecked()
        return {
            "provider": provider,
            "command": command,
            "workers": self.workers_spin.value(),
            "ai_mode": self.mode_combo.currentData(),
            "context_mode": self.context_mode.currentData(),
            "discard_pages": rule if self.clean_check.isChecked() else "",
            "clean_digital": self.clean_check.isChecked(),
            "auto_build_html": auto_build,
            "auto_build_hub": auto_build,
        }

