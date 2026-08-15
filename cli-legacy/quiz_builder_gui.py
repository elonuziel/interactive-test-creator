#!/usr/bin/env python3
"""
quiz_builder_gui.py — Modern Desktop GUI Application for Interactive Hebrew Quiz Builder
Features:
- Zero-dependency desktop interface built with Python standard library (tkinter/ttk)
- Dark & Light Theme system with modern slate aesthetics
- Multi-exam folder intake with flat-file auto-grouping
- Live status badges ([BUILT], [READY TO BUILD], [NEEDS EXTRACTION], [EMPTY])
- 1-Click action buttons per exam: Copy Web Prompt, Run CLI Agent, Open Quiz, Open Folder
- Batch runner toolbar (Run All, Build Ready, Open Master Portal, Watch Mode)
- Threaded background worker (non-blocking UI with live progress and activity logs)
- Search filter box
"""

import os
import sys
import json
import time
import queue
import shutil
import threading
import subprocess
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Resolve directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == 'cli-legacy' else SCRIPT_DIR
sys.path.insert(0, SCRIPT_DIR)

try:
    import quiz_builder_cli as cli
except ImportError:
    from . import quiz_builder_cli as cli

# Color Palettes
THEMES = {
    "dark": {
        "bg": "#0f172a",          # Slate 900
        "surface": "#1e293b",     # Slate 800
        "surface_card": "#1e293b",
        "card_hover": "#283548",
        "border": "#334155",      # Slate 700
        "text_primary": "#f8fafc",# Slate 50
        "text_secondary": "#94a3b8",# Slate 400
        "primary": "#3b82f6",     # Blue 500
        "primary_hover": "#2563eb",# Blue 600
        "primary_text": "#ffffff",
        "success": "#10b981",     # Emerald 500
        "success_bg": "#064e3b",
        "warning": "#f59e0b",     # Amber 500
        "warning_bg": "#78350f",
        "danger": "#ef4444",      # Red 500
        "input_bg": "#0f172a",
        "badge_built": "#059669",
        "badge_ready": "#2563eb",
        "badge_extract": "#d97706",
        "badge_empty": "#64748b",
        "log_bg": "#090d16",
        "log_fg": "#cbd5e1",
    },
    "light": {
        "bg": "#f8fafc",          # Slate 50
        "surface": "#ffffff",     # White
        "surface_card": "#ffffff",
        "card_hover": "#f1f5f9",
        "border": "#e2e8f0",      # Slate 200
        "text_primary": "#0f172a",# Slate 900
        "text_secondary": "#64748b",# Slate 500
        "primary": "#2563eb",     # Blue 600
        "primary_hover": "#1d4ed8",# Blue 700
        "primary_text": "#ffffff",
        "success": "#059669",     # Emerald 600
        "success_bg": "#d1fae5",
        "warning": "#d97706",     # Amber 600
        "warning_bg": "#fef3c7",
        "danger": "#dc2626",      # Red 600
        "input_bg": "#f1f5f9",
        "badge_built": "#059669",
        "badge_ready": "#2563eb",
        "badge_extract": "#d97706",
        "badge_empty": "#64748b",
        "log_bg": "#1e293b",
        "log_fg": "#f8fafc",
    }
}


class QuizBuilderGUI:
    def __init__(self, root, initial_dir=None):
        self.root = root
        self.root.title("📚 Interactive Hebrew Quiz Builder — Desktop App")
        self.root.geometry("1020x760")
        self.root.minsize(860, 600)

        # Set app icon if available
        self.theme_name = "dark"
        self.colors = THEMES[self.theme_name]
        self.target_dir = initial_dir or os.path.join(SCRIPT_DIR, 'tests')
        if not os.path.isdir(self.target_dir):
            self.target_dir = os.path.join(REPO_ROOT, 'tests')
            if not os.path.isdir(self.target_dir):
                self.target_dir = os.getcwd()

        self.workspaces_info = []
        self.log_queue = queue.Queue()
        self.is_processing = False
        self.watch_active = False

        self._apply_theme_config()
        self._build_ui()
        self._start_log_consumer()
        self.refresh_workspaces()

    def _apply_theme_config(self):
        self.colors = THEMES[self.theme_name]
        self.root.configure(bg=self.colors["bg"])

    def _build_ui(self):
        # Main Layout Container
        self.main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # ── 1. Top Header Bar ───────────────────────────────────────────
        header_frame = tk.Frame(self.main_frame, bg=self.colors["surface"], bd=1, relief=tk.SOLID)
        header_frame.pack(fill=tk.X, pady=(0, 12))

        header_inner = tk.Frame(header_frame, bg=self.colors["surface"])
        header_inner.pack(fill=tk.X, padx=16, pady=12)

        # Title & Subtitle
        title_box = tk.Frame(header_inner, bg=self.colors["surface"])
        title_box.pack(side=tk.LEFT, fill=tk.Y)

        title_lbl = tk.Label(
            title_box,
            text="📚 Interactive Hebrew Quiz Builder",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["surface"],
            fg=self.colors["primary"]
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_box,
            text="Batch transform PDF/DOCX exams & answer keys into interactive standalone digital quizzes",
            font=("Segoe UI", 9),
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"]
        )
        sub_lbl.pack(anchor="w")

        # Top Right: Theme Switcher & Status
        top_right = tk.Frame(header_inner, bg=self.colors["surface"])
        top_right.pack(side=tk.RIGHT)

        self.theme_btn = tk.Button(
            top_right,
            text="☀️ Light Mode" if self.theme_name == "dark" else "🌙 Dark Mode",
            command=self.toggle_theme,
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            activeforeground=self.colors["text_primary"],
            relief=tk.FLAT,
            padx=10, pady=4,
            cursor="hand2"
        )
        self.theme_btn.pack(side=tk.RIGHT, padx=4)

        # ── 2. Folder Selector & Quick Action Toolbar ───────────────────
        toolbar_card = tk.Frame(self.main_frame, bg=self.colors["surface"], bd=1, relief=tk.SOLID)
        toolbar_card.pack(fill=tk.X, pady=(0, 12))

        tb_inner = tk.Frame(toolbar_card, bg=self.colors["surface"])
        tb_inner.pack(fill=tk.X, padx=14, pady=10)

        # Folder Path Row
        folder_row = tk.Frame(tb_inner, bg=self.colors["surface"])
        folder_row.pack(fill=tk.X, pady=(0, 8))

        folder_icon = tk.Label(folder_row, text="📁 Workspace:", font=("Segoe UI", 10, "bold"), bg=self.colors["surface"], fg=self.colors["text_primary"])
        folder_icon.pack(side=tk.LEFT, padx=(0, 6))

        self.folder_var = tk.StringVar(value=self.target_dir)
        self.folder_entry = tk.Entry(
            folder_row,
            textvariable=self.folder_var,
            font=("Segoe UI", 10),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            insertbackground=self.colors["text_primary"],
            relief=tk.FLAT,
            bd=1
        )
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=4)

        browse_btn = tk.Button(
            folder_row,
            text="📂 Browse Folder",
            command=self.browse_folder,
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["primary_text"],
            activebackground=self.colors["primary_hover"],
            activeforeground=self.colors["primary_text"],
            relief=tk.FLAT,
            padx=12, pady=4,
            cursor="hand2"
        )
        browse_btn.pack(side=tk.LEFT, padx=2)

        refresh_btn = tk.Button(
            folder_row,
            text="🔄 Refresh",
            command=self.refresh_workspaces,
            font=("Segoe UI", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=10, pady=4,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.LEFT, padx=2)

        # Action Buttons Row
        actions_row = tk.Frame(tb_inner, bg=self.colors["surface"])
        actions_row.pack(fill=tk.X, pady=(4, 0))

        self.batch_btn = tk.Button(
            actions_row,
            text="⚡ Run Batch All",
            command=self.run_batch_all,
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["success"],
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=14, pady=5,
            cursor="hand2"
        )
        self.batch_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.build_ready_btn = tk.Button(
            actions_row,
            text="🔨 Build Ready Quizzes",
            command=self.build_ready_quizzes,
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["primary_text"],
            activebackground=self.colors["primary_hover"],
            relief=tk.FLAT,
            padx=12, pady=5,
            cursor="hand2"
        )
        self.build_ready_btn.pack(side=tk.LEFT, padx=4)

        portal_btn = tk.Button(
            actions_row,
            text="🌐 Open Master Portal",
            command=self.open_master_portal,
            font=("Segoe UI", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=10, pady=5,
            cursor="hand2"
        )
        portal_btn.pack(side=tk.LEFT, padx=4)

        server_btn = tk.Button(
            actions_row,
            text="🚀 Local Web Server",
            command=self.start_web_server,
            font=("Segoe UI", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=10, pady=5,
            cursor="hand2"
        )
        server_btn.pack(side=tk.LEFT, padx=4)

        # Search Filter Box
        search_box = tk.Frame(actions_row, bg=self.colors["surface"])
        search_box.pack(side=tk.RIGHT)

        search_lbl = tk.Label(search_box, text="🔍 Search:", font=("Segoe UI", 9), bg=self.colors["surface"], fg=self.colors["text_secondary"])
        search_lbl.pack(side=tk.LEFT, padx=(0, 4))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_cards())
        search_entry = tk.Entry(
            search_box,
            textvariable=self.search_var,
            font=("Segoe UI", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            insertbackground=self.colors["text_primary"],
            width=18,
            relief=tk.FLAT,
            bd=1
        )
        search_entry.pack(side=tk.LEFT, ipady=3)

        # ── 3. Middle Content Area: Cards List + Progress ────────────────
        content_split = tk.PanedWindow(self.main_frame, orient=tk.VERTICAL, bg=self.colors["bg"], sashwidth=4)
        content_split.pack(fill=tk.BOTH, expand=True)

        # Top Pane: Scrollable Cards Container
        cards_outer = tk.Frame(content_split, bg=self.colors["bg"])
        content_split.add(cards_outer, minsize=260, height=380)

        # Statistics Bar
        self.stats_bar = tk.Frame(cards_outer, bg=self.colors["bg"])
        self.stats_bar.pack(fill=tk.X, pady=(0, 6))

        self.stats_label = tk.Label(
            self.stats_bar,
            text="Scanning exams...",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text_secondary"]
        )
        self.stats_label.pack(side=tk.LEFT)

        # Canvas for scrollable cards
        self.canvas = tk.Canvas(cards_outer, bg=self.colors["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(cards_outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_cards = tk.Frame(self.canvas, bg=self.colors["bg"])

        self.scrollable_cards.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_cards, anchor="nw")
        self.canvas.configure(xscrollcommand=None, yscrollcommand=self.scrollbar.set)

        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Pane: Progress & Activity Log Drawer
        log_pane = tk.Frame(content_split, bg=self.colors["surface"], bd=1, relief=tk.SOLID)
        content_split.add(log_pane, minsize=140, height=180)

        log_header = tk.Frame(log_pane, bg=self.colors["surface"])
        log_header.pack(fill=tk.X, padx=10, pady=(6, 4))

        log_title = tk.Label(log_header, text="📊 Live Activity & Pipeline Console", font=("Segoe UI", 9, "bold"), bg=self.colors["surface"], fg=self.colors["text_primary"])
        log_title.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(log_header, mode="determinate", length=220)
        self.progress_bar.pack(side=tk.RIGHT, padx=4)

        # Log Text Box
        self.log_text = tk.Text(
            log_pane,
            bg=self.colors["log_bg"],
            fg=self.colors["log_fg"],
            insertbackground=self.colors["text_primary"],
            font=("Consolas", 9),
            wrap=tk.WORD,
            bd=0,
            padx=8,
            pady=6
        )
        log_scroll = ttk.Scrollbar(log_pane, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=(0, 6))
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 6), padx=(0, 6))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Workspace Scanner & Cards Renderer ───────────────────────────
    def refresh_workspaces(self):
        """Scan workspace folder, auto-group, and render exam cards."""
        self.target_dir = self.folder_var.get().strip()
        if not os.path.isdir(self.target_dir):
            self.log("⚠️ Target folder does not exist: " + self.target_dir)
            return

        # Scan & auto-group
        tests_dir = os.path.join(SCRIPT_DIR, 'tests') if os.path.isdir(os.path.join(SCRIPT_DIR, 'tests')) else self.target_dir
        workspaces = cli.scan_and_group_inputs(self.target_dir, tests_dir)
        self.workspaces_info = [cli.analyze_workspace(w) for w in workspaces]

        self.render_cards(self.workspaces_info)
        self._update_stats_bar()

    def filter_cards(self):
        query = self.search_var.get().strip().lower()
        if not query:
            self.render_cards(self.workspaces_info)
            return
        filtered = [
            info for info in self.workspaces_info
            if query in info['name'].lower() or any(query in f.lower() for f in info.get('pdf_files', []) + info.get('docx_files', []))
        ]
        self.render_cards(filtered)

    def render_cards(self, workspaces):
        # Clear existing cards
        for widget in self.scrollable_cards.winfo_children():
            widget.destroy()

        if not workspaces:
            empty_box = tk.Frame(self.scrollable_cards, bg=self.colors["surface"], bd=1, relief=tk.SOLID)
            empty_box.pack(fill=tk.X, padx=12, pady=24)
            lbl = tk.Label(
                empty_box,
                text="📂 No exam folders or files found in this workspace.\nDrop .pdf, .docx, or .csv files into the folder and click Refresh!",
                font=("Segoe UI", 11),
                bg=self.colors["surface"],
                fg=self.colors["text_secondary"],
                pady=24
            )
            lbl.pack()
            return

        for info in workspaces:
            self._create_exam_card(info)

    def _create_exam_card(self, info):
        card = tk.Frame(
            self.scrollable_cards,
            bg=self.colors["surface_card"],
            bd=1,
            relief=tk.SOLID,
            highlightbackground=self.colors["border"],
            highlightthickness=1
        )
        card.pack(fill=tk.X, padx=6, pady=6)

        inner = tk.Frame(card, bg=self.colors["surface_card"])
        inner.pack(fill=tk.X, padx=14, pady=10)

        # Header Row: Title + Status Badge
        top_row = tk.Frame(inner, bg=self.colors["surface_card"])
        top_row.pack(fill=tk.X, pady=(0, 4))

        # Title
        display_title = info['name'].replace('_', ' ').title()
        title_lbl = tk.Label(
            top_row,
            text=f"📄 {display_title}",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["surface_card"],
            fg=self.colors["text_primary"]
        )
        title_lbl.pack(side=tk.LEFT)

        # Status Badge
        status = info.get('status', 'EMPTY')
        badge_colors = {
            "BUILT": (self.colors["badge_built"], "#ffffff", "✔ BUILT (READY TO SOLVE)"),
            "READY_TO_BUILD": (self.colors["badge_ready"], "#ffffff", "⚡ READY TO BUILD"),
            "READY_TO_PARSE": ("#0284c7", "#ffffff", "📝 READY TO PARSE (MD FOUND)"),
            "NEEDS_EXTRACTION": (self.colors["badge_extract"], "#ffffff", "⏳ NEEDS AI EXTRACTION"),
            "EMPTY": (self.colors["badge_empty"], "#ffffff", "⚪ EMPTY WORKSPACE"),
        }
        bg_col, fg_col, badge_text = badge_colors.get(status, (self.colors["badge_empty"], "#ffffff", status))

        badge_lbl = tk.Label(
            top_row,
            text=badge_text,
            font=("Segoe UI", 8, "bold"),
            bg=bg_col,
            fg=fg_col,
            padx=8,
            pady=2
        )
        badge_lbl.pack(side=tk.RIGHT)

        # Subtitle / Metadata Row
        meta_row = tk.Frame(inner, bg=self.colors["surface_card"])
        meta_row.pack(fill=tk.X, pady=(2, 8))

        src_str = "None"
        if info['pdf_files']:
            src_str = f"PDF: {info['pdf_files'][0]}"
        elif info['docx_files']:
            src_str = f"DOCX: {info['docx_files'][0]}"

        ans_str = f"Form {info['form_number']}"
        if info['csv_files']:
            ans_str += f" ({info['csv_files'][0]})"

        q_count_str = ""
        q_path = os.path.join(info['dir'], 'questions.json')
        if os.path.isfile(q_path):
            try:
                with open(q_path, 'r', encoding='utf-8') as qf:
                    cnt = len(json.load(qf))
                    q_count_str = f" • {cnt} Questions"
            except Exception:
                pass

        meta_lbl = tk.Label(
            meta_row,
            text=f"📁 {src_str}   │   🔑 {ans_str}{q_count_str}",
            font=("Segoe UI", 9),
            bg=self.colors["surface_card"],
            fg=self.colors["text_secondary"]
        )
        meta_lbl.pack(side=tk.LEFT)

        # Actions Buttons Row
        btn_row = tk.Frame(inner, bg=self.colors["surface_card"])
        btn_row.pack(fill=tk.X, pady=(4, 0))

        # 1. Copy Web Prompt Button
        copy_prompt_btn = tk.Button(
            btn_row,
            text="📋 Copy Web Prompt",
            command=lambda i=info: self.copy_web_prompt(i),
            font=("Segoe UI", 8, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=8, pady=3,
            cursor="hand2"
        )
        copy_prompt_btn.pack(side=tk.LEFT, padx=(0, 4))

        # 2. Run CLI Agent Button
        agent_btn = tk.Button(
            btn_row,
            text="🤖 Run CLI Agent",
            command=lambda i=info: self.run_agent_single(i),
            font=("Segoe UI", 8),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=8, pady=3,
            cursor="hand2"
        )
        agent_btn.pack(side=tk.LEFT, padx=4)

        # 3. Build HTML Button
        build_btn = tk.Button(
            btn_row,
            text="🔨 Build HTML",
            command=lambda i=info: self.build_single(i),
            font=("Segoe UI", 8),
            bg=self.colors["input_bg"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=8, pady=3,
            cursor="hand2"
        )
        build_btn.pack(side=tk.LEFT, padx=4)

        # 4. Open Quiz Button (if built)
        if info['html_files']:
            open_quiz_btn = tk.Button(
                btn_row,
                text="🚀 Solve Quiz",
                command=lambda i=info: self.open_quiz_single(i),
                font=("Segoe UI", 8, "bold"),
                bg=self.colors["primary"],
                fg="#ffffff",
                activebackground=self.colors["primary_hover"],
                relief=tk.FLAT,
                padx=10, pady=3,
                cursor="hand2"
            )
            open_quiz_btn.pack(side=tk.LEFT, padx=4)

        # 5. Open Explorer Folder
        open_folder_btn = tk.Button(
            btn_row,
            text="📂 Open Folder",
            command=lambda i=info: cli.open_in_explorer(i['dir']),
            font=("Segoe UI", 8),
            bg=self.colors["input_bg"],
            fg=self.colors["text_secondary"],
            activebackground=self.colors["border"],
            relief=tk.FLAT,
            padx=6, pady=3,
            cursor="hand2"
        )
        open_folder_btn.pack(side=tk.RIGHT, padx=2)

    def _update_stats_bar(self):
        total = len(self.workspaces_info)
        built = sum(1 for w in self.workspaces_info if w.get('status') == 'BUILT')
        ready = sum(1 for w in self.workspaces_info if w.get('status') in ['READY_TO_BUILD', 'READY_TO_PARSE'])
        needs_ai = sum(1 for w in self.workspaces_info if w.get('status') == 'NEEDS_EXTRACTION')
        self.stats_label.config(
            text=f"Total Exams: {total}   │   ✔ Built: {built}   │   ⚡ Ready to Build: {ready}   │   ⏳ Needs AI: {needs_ai}"
        )

    # ── Card Actions ─────────────────────────────────────────────────
    def copy_web_prompt(self, info):
        """Copy the web AI prompt for this exam to the OS clipboard."""
        test_dir = info['dir']
        test_name = info['name']
        form_number = info['form_number']
        has_answers_flag = "1" if info['csv_files'] else "0"

        # Generate prompt if missing
        web_prompt_path = os.path.join(test_dir, 'prompt_web_ai.txt')
        if not os.path.isfile(web_prompt_path):
            cli.run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag, 'web'])

        if os.path.isfile(web_prompt_path):
            with open(web_prompt_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
            self.root.clipboard_clear()
            self.root.clipboard_append(prompt_text)
            self.log(f"📋 Copied Web AI prompt for '{test_name}' to clipboard!")
            messagebox.showinfo("Prompt Copied!", f"The Web AI prompt for '{test_name}' has been copied to your clipboard.\nPaste it into ChatGPT, Claude.ai, or Gemini Web!")
        else:
            self.log(f"⚠️ Could not generate prompt for {test_name}")

    def run_agent_single(self, info):
        """Launch terminal CLI agent for a single workspace."""
        agent = cli.detect_cli_agent()
        if not agent:
            messagebox.showwarning("No CLI Agent Detected", "No local CLI agent (agy, gemini, claude) was detected in your PATH.\nUse 'Copy Web Prompt' instead to paste into web AI!")
            return

        test_dir = info['dir']
        test_name = info['name']
        form_number = info['form_number']
        has_answers = "1" if info['csv_files'] else "0"

        # Generate local prompt
        cli.run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers, 'local'])
        prompt_path = os.path.join(test_dir, 'prompt_local_agent.txt')

        self.log(f"🤖 Dispatching {agent} for {test_name}...")
        try:
            if sys.platform == 'win32':
                cmd_str = f'type "{prompt_path}" | {agent}'
                subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', cmd_str], shell=True)
            else:
                subprocess.Popen([agent], stdin=open(prompt_path, 'r'))
        except Exception as e:
            self.log(f"❌ Error launching agent: {e}")

    def build_single(self, info):
        """Run post-processing & HTML build for a single workspace."""
        def worker():
            self.set_processing_state(True)
            self.log(f"🔨 Building workspace: {info['name']}...")
            res = cli.process_workspace_auto(info['dir'], auto_confirm=True)
            if res:
                self.log(f"✔ Successfully built {info['name']} -> {res}")
            else:
                self.log(f"⚠️ Build finished for {info['name']}")
            self.set_processing_state(False)
            self.root.after(0, self.refresh_workspaces)

        threading.Thread(target=worker, daemon=True).start()

    def open_quiz_single(self, info):
        """Open compiled HTML quiz in default browser."""
        if info['html_files']:
            html_p = os.path.join(info['dir'], info['html_files'][0])
            webbrowser.open(html_p)

    # ── Toolbar Action Handlers ──────────────────────────────────────
    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.target_dir, title="Select Exam Workspace Folder")
        if chosen:
            self.folder_var.set(chosen)
            self.refresh_workspaces()

    def run_batch_all(self):
        """Run the automated batch pipeline across all workspaces in background."""
        if self.is_processing:
            return

        def worker():
            self.set_processing_state(True)
            self.log("🚀 Starting Batch Pipeline for all detected workspaces...")
            output_dir = os.path.join(SCRIPT_DIR, 'output')
            cli.run_batch_pipeline(self.target_dir, auto_confirm=True, output_dir=output_dir)
            self.log("🎉 Batch Pipeline completed!")
            self.set_processing_state(False)
            self.root.after(0, self.refresh_workspaces)

        threading.Thread(target=worker, daemon=True).start()

    def build_ready_quizzes(self):
        """Quickly build HTML for all ready workspaces."""
        if self.is_processing:
            return

        def worker():
            self.set_processing_state(True)
            self.log("🔨 Compiling all ready workspaces...")
            output_dir = os.path.join(SCRIPT_DIR, 'output')
            cli.run_batch_pipeline(self.target_dir, auto_confirm=True, build_only=True, output_dir=output_dir)
            self.log("✔ Ready workspaces built successfully!")
            self.set_processing_state(False)
            self.root.after(0, self.refresh_workspaces)

        threading.Thread(target=worker, daemon=True).start()

    def open_master_portal(self):
        output_dir = os.path.join(SCRIPT_DIR, 'output')
        portal_path = os.path.join(output_dir, 'index.html')
        if not os.path.isfile(portal_path):
            # Generate on the fly
            built = []
            for w in self.workspaces_info:
                if w.get('html_files'):
                    built.append({
                        'name': w['name'],
                        'title': w['name'].replace('_', ' ').title(),
                        'question_count': 0,
                        'html_name': f"{w['name']}.html",
                    })
            portal_path = cli.generate_master_portal(output_dir, built)
        webbrowser.open(portal_path)

    def start_web_server(self):
        self.log("🚀 Launching local web server on port 8000...")
        cli.start_local_server(8000)

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self._apply_theme_config()
        self.main_frame.destroy()
        self._build_ui()
        self.refresh_workspaces()

    # ── Progress & Log Utilities ─────────────────────────────────────
    def log(self, message):
        self.log_queue.put(message)

    def _start_log_consumer(self):
        def check_logs():
            while not self.log_queue.empty():
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                self.log_text.see(tk.END)
            self.root.after(100, check_logs)
        self.root.after(100, check_logs)

    def set_processing_state(self, is_processing):
        self.is_processing = is_processing
        if is_processing:
            self.progress_bar.start(10)
            self.batch_btn.config(state=tk.DISABLED)
            self.build_ready_btn.config(state=tk.DISABLED)
        else:
            self.progress_bar.stop()
            self.batch_btn.config(state=tk.NORMAL)
            self.build_ready_btn.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    # Check for initial folder from arguments
    initial_folder = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None
    app = QuizBuilderGUI(root, initial_dir=initial_folder)
    root.mainloop()


if __name__ == '__main__':
    main()
