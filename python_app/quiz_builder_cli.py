#!/usr/bin/env python3
"""
quiz_builder_cli.py — Modernized Streamlined Batch Hebrew Quiz Builder & Local Server
Features:
- Multi-exam folder-drop & flat-file auto-grouping
- 1-Screen Quick Confirmation summary table
- Batch DOCX to PDF auto-conversion
- Automated PDF rendering, text extraction, and QA checks
- Terminal AI Agent auto-dispatch (agy, gemini, claude) or Web AI prompts + BATCH_PROMPTS_INDEX.md
- Standalone single-file HTML quiz compilation
- Master Quiz Portal (output/index.html) with search & stats
- Fast --build and --watch modes
"""

import os
import sys
import json
import re
import glob
import runpy
import shutil
import mimetypes
import base64
import argparse
import subprocess
import http.server
import socketserver
import webbrowser
import threading
import time
from pathlib import Path

# Ensure UTF-8 output and enable Windows Virtual Terminal ANSI color mode
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        os.system('')

# PyMuPDF, pandas, openpyxl imports
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pandas as pd
except ImportError:
    pd = None

# ANSI colors for terminal UI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_RED = "\033[31m"
C_GRAY = "\033[90m"
C_WHITE = "\033[97m"

# Path setup: Resolve actual directory where the .exe or script is executed
if getattr(sys, 'frozen', False):
    CLI_ROOT = os.path.dirname(os.path.abspath(sys.executable))
    MEI_DIR = getattr(sys, '_MEIPASS', CLI_ROOT)
    PYTHON_SCRIPTS_DIR = os.path.join(MEI_DIR, 'python_scripts')
    if not os.path.isdir(PYTHON_SCRIPTS_DIR):
        PYTHON_SCRIPTS_DIR = os.path.join(MEI_DIR, 'python_app', 'python_scripts')
        if not os.path.isdir(PYTHON_SCRIPTS_DIR):
            PYTHON_SCRIPTS_DIR = os.path.join(MEI_DIR, 'cli-legacy', 'python_scripts')
else:
    CLI_ROOT = os.path.dirname(os.path.abspath(__file__))
    MEI_DIR = CLI_ROOT
    PYTHON_SCRIPTS_DIR = os.path.join(CLI_ROOT, 'python_scripts')

REPO_ROOT = os.path.dirname(CLI_ROOT) if os.path.basename(CLI_ROOT) in ['python_app', 'cli-legacy'] else CLI_ROOT
TESTS_DIR = os.path.join(REPO_ROOT, 'tests') if os.path.isdir(os.path.join(REPO_ROOT, 'tests')) else os.path.join(CLI_ROOT, 'tests')
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, 'output')


# =========================================================================
# System & Utility Helpers
# =========================================================================

def copy_to_clipboard(text):
    if sys.platform == 'win32':
        try:
            p = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode('utf-8'))
            return True
        except Exception:
            pass
    return False


def open_in_explorer(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    if sys.platform == 'win32':
        try:
            os.startfile(path)
        except Exception:
            subprocess.Popen(['explorer', path])
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


def find_soffice_binary():
    """Find a LibreOffice soffice executable if available."""
    cand = shutil.which('soffice')
    if cand:
        return cand

    if sys.platform == 'win32':
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for p in common_paths:
            if os.path.isfile(p):
                return p
    return None


def has_word_com():
    """Check whether Microsoft Word COM automation is available on Windows."""
    if sys.platform != 'win32':
        return False
    if not shutil.which('powershell'):
        return False

    probe_cmd = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject Word.Application;"
        "$w.Quit();"
        "Write-Output 'ok'"
    )
    try:
        res = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', probe_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def detect_docx_converter():
    """Return a converter backend tuple: (backend_name, backend_value)."""
    soffice_path = find_soffice_binary()
    if soffice_path:
        return ('soffice', soffice_path)
    if has_word_com():
        return ('wordcom', 'powershell')
    return (None, None)


def convert_docx_to_pdf_with_soffice(soffice_path, docx_path, output_dir):
    cmd = [
        soffice_path,
        '--headless',
        '--convert-to',
        'pdf:writer_pdf_Export',
        '--outdir',
        output_dir,
        docx_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    return res.returncode == 0, (res.stderr or res.stdout or '').strip()


def convert_docx_to_pdf_with_wordcom(docx_path, pdf_path):
    safe_docx = docx_path.replace("'", "''")
    safe_pdf = pdf_path.replace("'", "''")
    ps_script = (
        "$ErrorActionPreference='Stop';"
        f"$docx='{safe_docx}';"
        f"$pdf='{safe_pdf}';"
        "$word=New-Object -ComObject Word.Application;"
        "$word.Visible=$false;"
        "$word.DisplayAlerts=0;"
        "$doc=$word.Documents.Open($docx, $false, $true);"
        "$doc.SaveAs([ref]$pdf, [ref]17);"
        "$doc.Close();"
        "$word.Quit();"
        "Write-Output 'ok'"
    )
    res = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps_script],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return res.returncode == 0, (res.stderr or res.stdout or '').strip()


def convert_docx_batch(docx_files, test_dir, backend_name, backend_value, overwrite_existing=False):
    """Convert DOCX files to PDFs in-place. Returns summary dict."""
    converted = []
    skipped = []
    failed = []

    for docx_name in docx_files:
        docx_path = os.path.join(test_dir, docx_name)
        base_name = os.path.splitext(docx_name)[0]
        expected_pdf = os.path.join(test_dir, f"{base_name}.pdf")

        if os.path.exists(expected_pdf) and not overwrite_existing:
            skipped.append((docx_name, 'matching PDF already exists'))
            continue

        try:
            if backend_name == 'soffice':
                ok, msg = convert_docx_to_pdf_with_soffice(backend_value, docx_path, test_dir)
            elif backend_name == 'wordcom':
                ok, msg = convert_docx_to_pdf_with_wordcom(docx_path, expected_pdf)
            else:
                ok, msg = False, 'no conversion backend configured'
        except Exception as exc:
            ok, msg = False, str(exc)

        if ok and os.path.isfile(expected_pdf):
            converted.append((docx_name, os.path.basename(expected_pdf)))
        else:
            failed.append((docx_name, msg or 'unknown conversion error'))

    return {
        'converted': converted,
        'skipped': skipped,
        'failed': failed,
    }


def detect_cli_agent():
    """Detect available CLI AI agents in PATH."""
    for ag in ['agy', 'gemini', 'claude', 'cursor']:
        if shutil.which(ag):
            return ag
    return None


def is_pdf_digital(pdf_path):
    if fitz is None:
        return False
    try:
        doc = fitz.open(pdf_path)
        pages_checked = min(3, len(doc))
        if pages_checked == 0:
            return False
        total_chars = sum(len(doc[i].get_text().strip()) for i in range(pages_checked))
        avg = total_chars / pages_checked
        return avg >= 50
    except Exception:
        return False


def run_script(script_name, args):
    """Run a pipeline script in-process to guarantee PyInstaller compatibility."""
    candidate_paths = [
        os.path.join(PYTHON_SCRIPTS_DIR, script_name),
        os.path.join(MEI_DIR, 'python_scripts', script_name),
        os.path.join(MEI_DIR, 'python_app', 'python_scripts', script_name),
        os.path.join(MEI_DIR, 'cli-legacy', 'python_scripts', script_name),
        os.path.join(CLI_ROOT, 'python_scripts', script_name),
    ]

    script_path = None
    for cand in candidate_paths:
        if os.path.isfile(cand):
            script_path = cand
            break

    if not script_path:
        print(f"  {C_RED}[✘] Script {script_name} not found in {PYTHON_SCRIPTS_DIR}{C_RESET}")
        return 1

    old_argv = sys.argv
    sys.argv = [script_path] + list(args)
    try:
        runpy.run_path(script_path, run_name='__main__')
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except Exception as e:
        print(f"  {C_RED}[✘] Error executing {script_name}: {e}{C_RESET}")
        return 1
    finally:
        sys.argv = old_argv


def cleanup_workspace_folder(test_dir):
    """Clean up scratch files, prompt txt files, clean merged PDFs, and unused page renders."""
    scratch_files = [
        'raw_text.md',
        'pdf_type_result.txt',
        'page_map.json',
        'prompt_local_agent.txt',
        'prompt_local_agent_enhanced.txt',
        'prompt_web_ai.txt',
        'prompt_web_ai_enhanced.txt',
        'prompt_proofread.txt',
        'prompt_proofread_local.txt',
        'prompt_proofread_web.txt',
        'final_questions.json',
        'output.json',
        'response.json',
        'data.json',
    ]
    cleaned = 0
    for sf in scratch_files:
        fp = os.path.join(test_dir, sf)
        if os.path.isfile(fp):
            try:
                os.remove(fp)
                cleaned += 1
            except Exception:
                pass

    # Delete any clean merged PDFs (*_clean.pdf) and leftover prompt .txt files
    for fname in os.listdir(test_dir):
        if fname.lower().endswith('_clean.pdf') or (fname.lower().startswith('prompt_') and fname.lower().endswith('.txt')):
            fp = os.path.join(test_dir, fname)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                    cleaned += 1
                except Exception:
                    pass

    # Check which page images / embedded images are referenced in questions.json
    q_file = os.path.join(test_dir, 'questions.json')
    referenced_images = set()
    if os.path.isfile(q_file):
        try:
            with open(q_file, 'r', encoding='utf-8') as f:
                qs = json.load(f)
            for q in qs:
                if isinstance(q, dict):
                    if q.get('pageImage'):
                        referenced_images.add(os.path.normpath(q['pageImage']))
                    if q.get('image'):
                        referenced_images.add(os.path.normpath(q['image']))
        except Exception:
            pass

    # Smart clean pages_output/ — keep ONLY page PNGs referenced in questions.json
    pages_dir = os.path.join(test_dir, 'pages_output')
    deleted_pages = 0
    kept_pages = 0
    if os.path.isdir(pages_dir):
        page_files = os.listdir(pages_dir)
        for pf in page_files:
            full_path = os.path.join(pages_dir, pf)
            if os.path.isfile(full_path):
                rel_path = os.path.normpath(os.path.join('pages_output', pf))
                if rel_path in referenced_images or any(ref.endswith(pf) for ref in referenced_images):
                    kept_pages += 1
                else:
                    try:
                        os.remove(full_path)
                        deleted_pages += 1
                    except Exception:
                        pass

        if kept_pages == 0 and len(os.listdir(pages_dir)) == 0:
            try:
                os.rmdir(pages_dir)
            except Exception:
                pass

    return cleaned, deleted_pages


# =========================================================================
# Intake & Auto-Grouping Engine
# =========================================================================

def normalize_stem_name(filename):
    """Derive clean exam stem name by stripping answer key suffixes."""
    stem = os.path.splitext(filename)[0]
    # Remove trailing answer/key/form indicators
    stem = re.sub(r'([_\-\s]+(answers?|ans|key|solutions?|פתרונות|תשובות|form\d+|טופס\d+))+$', '', stem, flags=re.IGNORECASE)
    stem = stem.strip('_- ')
    return stem or os.path.splitext(filename)[0]


def scan_and_group_inputs(target_dir, tests_dir=None):
    """
    Scan a target directory for flat exam files or subfolders,
    auto-grouping matching files into test workspaces.
    """
    if tests_dir is None:
        tests_dir = os.path.join(CLI_ROOT, 'tests')
    os.makedirs(tests_dir, exist_ok=True)

    if not os.path.exists(target_dir):
        return []

    entries = os.listdir(target_dir)
    subdirs = [d for d in entries if os.path.isdir(os.path.join(target_dir, d)) and not d.startswith('.')]
    flat_files = [f for f in entries if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith('.')]

    # Check if target_dir itself is already tests_dir
    is_same_tests_dir = (os.path.abspath(target_dir) == os.path.abspath(tests_dir))

    # Auto-group flat files by stem
    groups = {}
    valid_exts = ('.pdf', '.docx', '.csv', '.xlsx', '.xls', '.md', '.json', '.txt')
    for fname in flat_files:
        if fname.lower().endswith(valid_exts) and fname.lower() not in ['manifest.json', 'batch_prompts_index.md']:
            stem = normalize_stem_name(fname)
            groups.setdefault(stem, []).append(fname)

    # Move/Copy flat files into organized test folders
    for stem, files in groups.items():
        # Check if contains at least one PDF or DOCX or questions file
        has_exam_core = any(f.lower().endswith(('.pdf', '.docx', '.json', '.md')) for f in files)
        if not has_exam_core:
            continue

        workspace_path = os.path.join(tests_dir, stem)
        os.makedirs(workspace_path, exist_ok=True)
        for fname in files:
            src = os.path.join(target_dir, fname)
            dst = os.path.join(workspace_path, fname)
            if src != dst and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass

    # Include existing subdirectories
    for d in subdirs:
        sub_path = os.path.join(target_dir, d)
        if not is_same_tests_dir:
            dst_sub = os.path.join(tests_dir, d)
            if not os.path.exists(dst_sub):
                try:
                    shutil.copytree(sub_path, dst_sub)
                except Exception:
                    pass

    # Return all valid workspaces inside tests_dir
    workspaces = []
    if os.path.isdir(tests_dir):
        for entry in sorted(os.listdir(tests_dir)):
            full_p = os.path.join(tests_dir, entry)
            if os.path.isdir(full_p) and not entry.startswith('.'):
                workspaces.append(full_p)

    return workspaces


def analyze_workspace(test_dir):
    """Analyze a test workspace directory and return structured metadata."""
    name = os.path.basename(os.path.normpath(test_dir))
    files = os.listdir(test_dir) if os.path.isdir(test_dir) else []

    pdf_files = [f for f in files if f.lower().endswith('.pdf') and not f.lower().endswith('_clean.pdf')]
    docx_files = [f for f in files if f.lower().endswith('.docx')]
    csv_files = [f for f in files if f.lower().endswith(('.csv', '.xlsx', '.xls'))]
    html_files = [f for f in files if f.lower().endswith('.html')]

    has_q_json = os.path.isfile(os.path.join(test_dir, 'questions.json'))
    has_q_md = any(f.lower() in ['questions.md', 'output.md', 'questions.txt'] for f in files)
    pages_dir = os.path.join(test_dir, 'pages_output')
    has_pages = os.path.isdir(pages_dir) and len(os.listdir(pages_dir)) > 0

    # Auto-detect form number from answer filename or default
    form_num = "0"
    if csv_files:
        form_match = re.search(r'form[_\-\s]*(\d+)', csv_files[0], re.IGNORECASE)
        if form_match:
            form_num = form_match.group(1)
        else:
            form_num = "1"

    # Determine status
    if html_files and has_q_json:
        status = "BUILT"
    elif has_q_json:
        status = "READY_TO_BUILD"
    elif has_q_md:
        status = "READY_TO_PARSE"
    elif pdf_files or docx_files:
        status = "NEEDS_EXTRACTION"
    else:
        status = "EMPTY"

    return {
        'name': name,
        'dir': test_dir,
        'pdf_files': pdf_files,
        'docx_files': docx_files,
        'csv_files': csv_files,
        'html_files': html_files,
        'has_questions_json': has_q_json,
        'has_questions_md': has_q_md,
        'has_pages': has_pages,
        'form_number': form_num,
        'status': status,
    }


# =========================================================================
# 1-Screen Summary & Batch Confirmation UI
# =========================================================================

def print_header():
    print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_BOLD}{C_WHITE}         INTERACTIVE HEBREW QUIZ BUILDER (BATCH RUNNER)                   {C_RESET} {C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_GRAY}  Batch Transform Exams & Answer Keys into Interactive Standalone Quizzes {C_RESET} {C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")


def display_batch_summary(workspaces_info, agent_found=None, converter_name=None):
    """Print a 1-screen summary table of all detected tests & environment status."""
    print(f"{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_BOLD}🚀 BATCH EXAM SUMMARY ({len(workspaces_info)} Exam{'s' if len(workspaces_info) != 1 else ''} Found){C_RESET}{' ' * max(0, 48 - len(str(len(workspaces_info))))}{C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}├────┬──────────────────────┬────────────────────────┬─────────────┬───────────────┤{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_BOLD}#  │ Exam Name            │ Source File            │ Form / Key  │ Status        {C_RESET}{C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}├────┼──────────────────────┼────────────────────────┼─────────────┼───────────────┤{C_RESET}")

    status_badges = {
        "BUILT": f"{C_GREEN}[BUILT]{C_RESET}",
        "READY_TO_BUILD": f"{C_GREEN}[READY BUILD]{C_RESET}",
        "READY_TO_PARSE": f"{C_CYAN}[READY PARSE]{C_RESET}",
        "NEEDS_EXTRACTION": f"{C_YELLOW}[EXTRACTION]{C_RESET}",
        "EMPTY": f"{C_GRAY}[EMPTY]{C_RESET}",
    }

    for idx, info in enumerate(workspaces_info, 1):
        name = (info['name'][:20] + '..') if len(info['name']) > 20 else info['name']
        src = "None"
        if info['pdf_files']:
            src = info['pdf_files'][0]
        elif info['docx_files']:
            src = info['docx_files'][0] + " (DOCX)"
        src = (src[:22] + '..') if len(src) > 22 else src

        ans = f"Form {info['form_number']}"
        if info['csv_files']:
            ans += f" ({info['csv_files'][0][:8]})"
        ans = (ans[:11] + '..') if len(ans) > 11 else ans

        badge = status_badges.get(info['status'], f"[{info['status']}]")
        print(f"{C_CYAN}│{C_RESET} {idx:<2} │ {name:<20} │ {src:<22} │ {ans:<11} │ {badge:<22} {C_CYAN}│{C_RESET}")

    print(f"{C_CYAN}└────┴──────────────────────┴────────────────────────┴─────────────┴───────────────┘{C_RESET}")

    agent_str = f"{C_GREEN}{agent_found} (Ready){C_RESET}" if agent_found else f"{C_YELLOW}None (Web Prompt Mode){C_RESET}"
    conv_str = f"{C_GREEN}{converter_name}{C_RESET}" if converter_name else f"{C_GRAY}None (Manual PDF){C_RESET}"

    print(f"  🤖 {C_BOLD}CLI Agent:{C_RESET} {agent_str}  │  📄 {C_BOLD}DOCX Converter:{C_RESET} {conv_str}\n")


# =========================================================================
# Master Portal HTML Generator
# =========================================================================

def generate_master_portal(output_dir, built_quizzes):
    """
    Generate output/index.html containing a master dashboard
    to launch all generated interactive quizzes.
    """
    os.makedirs(output_dir, exist_ok=True)
    portal_path = os.path.join(output_dir, 'index.html')

    quiz_cards_html = []
    for q in built_quizzes:
        name = q.get('name', 'Quiz')
        title = q.get('title', name.replace('_', ' ').title())
        q_count = q.get('question_count', 0)
        rel_html = q.get('html_name', f"{name}.html")

        quiz_cards_html.append(f"""
        <div class="quiz-card" data-title="{title.lower()} {name.lower()}">
            <div class="card-header">
                <span class="quiz-badge">{q_count} שאלות</span>
                <span class="status-dot"></span>
            </div>
            <h2 class="quiz-title">{title}</h2>
            <div class="quiz-meta">
                <span>📁 {name}</span>
                <span>⚡ ציון מיידי</span>
            </div>
            <a href="{rel_html}" class="launch-btn" target="_blank">פתור מבחן כעת ←</a>
        </div>
        """)

    cards_joined = "\n".join(quiz_cards_html) if quiz_cards_html else "<p class='no-quizzes'>לא נמצאו מבחנים מוכנים. הרץ את quiz_builder כדי ליצור מבחנים!</p>"

    html_content = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>פורטל המבחנים האינטראקטיביים | Master Quiz Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --border: #334155;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Rubik', sans-serif; }}
        body {{ background-color: var(--bg-color); color: var(--text-primary); min-height: 100vh; padding: 2rem 1rem; }}
        .portal-container {{ max-width: 1000px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 2.5rem; }}
        header h1 {{ font-size: 2.4rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }}
        header p {{ color: var(--text-secondary); font-size: 1.1rem; }}
        .stats-bar {{ display: flex; gap: 1rem; justify-content: center; margin: 1.5rem 0; flex-wrap: wrap; }}
        .stat-pill {{ background: var(--card-bg); border: 1px solid var(--border); padding: 0.5rem 1.2rem; border-radius: 9999px; font-size: 0.9rem; color: var(--text-secondary); }}
        .stat-pill strong {{ color: var(--text-primary); }}
        .search-box {{ margin-bottom: 2rem; display: flex; justify-content: center; }}
        .search-input {{ width: 100%; max-width: 500px; padding: 0.85rem 1.5rem; border-radius: 9999px; background: var(--card-bg); border: 1px solid var(--border); color: var(--text-primary); font-size: 1rem; outline: none; transition: border-color 0.2s; text-align: right; }}
        .search-input:focus {{ border-color: var(--primary); }}
        .quiz-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }}
        .quiz-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s; }}
        .quiz-card:hover {{ transform: translateY(-4px); border-color: var(--primary); box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }}
        .quiz-badge {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }}
        .status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--success); display: inline-block; }}
        .quiz-title {{ font-size: 1.25rem; font-weight: 700; margin-bottom: 1rem; line-height: 1.4; }}
        .quiz-meta {{ font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.5rem; display: flex; justify-content: space-between; }}
        .launch-btn {{ display: block; text-align: center; background: linear-gradient(135deg, var(--primary), var(--primary-hover)); color: white; text-decoration: none; padding: 0.75rem; border-radius: 0.5rem; font-weight: 600; font-size: 0.95rem; transition: filter 0.2s; }}
        .launch-btn:hover {{ filter: brightness(1.1); }}
        .no-quizzes {{ text-align: center; color: var(--text-secondary); grid-column: 1 / -1; padding: 3rem; }}
    </style>
</head>
<body>
    <div class="portal-container">
        <header>
            <h1>📚 פורטל המבחנים האינטראקטיביים</h1>
            <p>מבחנים דיגיטליים עצמאיים לתרגול אינטראקטיבי עם בדיקה מיידית וסימון שאלות</p>
            <div class="stats-bar">
                <div class="stat-pill">סה"כ מבחנים: <strong>{len(built_quizzes)}</strong></div>
                <div class="stat-pill">סה"כ שאלות: <strong>{sum(q.get('question_count', 0) for q in built_quizzes)}</strong></div>
                <div class="stat-pill">מצב: <strong>100% עצמאי (Offline)</strong></div>
            </div>
        </header>

        <div class="search-box">
            <input type="text" class="search-input" id="quizSearch" placeholder="🔍 חפש מבחן לפי שם או נושא..." oninput="filterQuizzes()">
        </div>

        <div class="quiz-grid" id="quizGrid">
            {cards_joined}
        </div>
    </div>

    <script>
        function filterQuizzes() {{
            const query = document.getElementById('quizSearch').value.toLowerCase();
            const cards = document.querySelectorAll('.quiz-card');
            cards.forEach(card => {{
                const title = card.getAttribute('data-title') || '';
                card.style.display = title.includes(query) ? 'flex' : 'none';
            }});
        }}
    </script>
</body>
</html>"""

    with open(portal_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return portal_path


# =========================================================================
# Single Workspace Pipeline Runner
# =========================================================================

def process_workspace_auto(test_dir, agent_choice=None, auto_confirm=True):
    """
    Run the end-to-end automated processing pipeline for a single test workspace.
    Returns path to built HTML if successful, or None.
    """
    test_name = os.path.basename(os.path.normpath(test_dir))
    info = analyze_workspace(test_dir)

    print(f"\n{C_BOLD}▶ Processing Workspace: {C_CYAN}{test_name}{C_RESET}")

    converted_pdf_names = []
    if info['docx_files']:
        backend_name, backend_value = detect_docx_converter()
        if backend_name:
            print(f"  {C_CYAN}[i] Converting DOCX to PDF ({backend_name})...{C_RESET}")
            summary = convert_docx_batch(info['docx_files'], test_dir, backend_name, backend_value)
            for src, dst in summary['converted']:
                converted_pdf_names.append(dst)
                print(f"  {C_GREEN}[✔] Converted {src} -> {dst}{C_RESET}")
        else:
            print(f"  {C_YELLOW}[!] No local DOCX-to-PDF converter was detected.{C_RESET}")
            if sys.stdin.isatty():
                open_in_explorer(test_dir)
                input("  Press Enter after exporting DOCX files to PDF...")
        info = analyze_workspace(test_dir)

    pdf_files = sorted(info['pdf_files'], key=lambda x: x.lower())
    if not pdf_files:
        print(f"  {C_YELLOW}[!] No PDF file in {test_name}. Skipping.{C_RESET}")
        return None

    if converted_pdf_names:
        preferred = [p for p in converted_pdf_names if p in pdf_files]
        selected_pdf = preferred[0] if preferred else pdf_files[0]
    else:
        selected_pdf = pdf_files[0]
    pdf_path = os.path.join(test_dir, selected_pdf)

    # 2. Format analysis & Page rendering
    run_script('1_detect_pdf_type.py', [pdf_path])
    is_digital = is_pdf_digital(pdf_path)
    if not info['has_pages']:
        print(f"  {C_CYAN}[i] Rendering clean PDF pages...{C_RESET}")
        out_pages = os.path.join(test_dir, 'pages_output')
        clean_pdf = os.path.join(test_dir, f"{test_name}_clean.pdf")
        run_script('3_render_pdf_pages.py', [pdf_path, '-o', out_pages, '--discard-pages', 'std', '--merged-pdf', clean_pdf])

        if is_digital:
            print(f"  {C_GREEN}[✔] Digital PDF detected: Extracting text...{C_RESET}")
            raw_md = os.path.join(test_dir, 'raw_text.md')
            img_dir = os.path.join(test_dir, 'images')
            page_map = os.path.join(test_dir, 'page_map.json')
            q_out = os.path.join(test_dir, 'questions.json')
            run_script('2_extract_text_fitz.py', [pdf_path, '-o', raw_md, '--extract-images', img_dir, '--page-map', page_map])
            run_script('5_parse_questions_md.py', [raw_md, '-o', q_out, '--image-dir', img_dir, '--page-map', page_map])

    # 3. Answer Key extraction
    out_ans = os.path.join(test_dir, 'answers.json')
    if info['csv_files']:
        csv_file = os.path.join(test_dir, info['csv_files'][0])
        print(f"  {C_CYAN}[i] Extracting answer key from {info['csv_files'][0]} (Form {info['form_number']})...{C_RESET}")
        run_script('4_extract_csv_answers.py', [csv_file, info['form_number'], '-o', out_ans])
    elif not os.path.exists(out_ans):
        print(f"  {C_CYAN}[i] Setting baseline Form 0 answers...{C_RESET}")
        run_script('4_extract_csv_answers.py', ['none', '0', '-o', out_ans])

    # 4. Generate Prompts / Dispatch Agent
    has_answers_flag = "1" if os.path.isfile(out_ans) else "0"
    detected_agent = detect_cli_agent() if agent_choice in [None, 'auto'] else (agent_choice if agent_choice != 'none' else None)

    if detected_agent and not os.path.exists(os.path.join(test_dir, 'questions.json')):
        print(f"  {C_CYAN}[i] Generating prompt and dispatching CLI agent: {detected_agent}...{C_RESET}")
        run_script('generate_prompts.py', [test_dir, test_name, info['form_number'], has_answers_flag, 'local'])
        prompt_path = os.path.join(test_dir, 'prompt_local_agent.txt')
        if os.path.isfile(prompt_path):
            try:
                if sys.platform == 'win32':
                    cmd_str = f'type "{prompt_path}" | {detected_agent}'
                    subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', cmd_str], shell=True)
                else:
                    subprocess.Popen([detected_agent], stdin=open(prompt_path, 'r'))
            except Exception as e:
                print(f"  {C_YELLOW}[!] Could not launch agent: {e}{C_RESET}")
    else:
        run_script('generate_prompts.py', [test_dir, test_name, info['form_number'], has_answers_flag, 'all'])

    # 5. Markdown / JSON post-processing & Validation
    q_final = os.path.join(test_dir, 'questions.json')
    run_step6(test_name, test_dir, q_final, auto_build=True)

    # Check if HTML built
    html_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.html')]
    if html_files:
        return os.path.join(test_dir, html_files[0])
    return None


def run_step6(test_name, test_dir, q_final, auto_build=True):
    """Auto-detect Markdown, merge answers, validate JSON schema, and build HTML."""
    # Check for Markdown questions file
    md_candidates = ['questions.md', 'output.md', 'questions.txt']
    found_md = None
    for cand in md_candidates:
        cand_p = os.path.join(test_dir, cand)
        if os.path.exists(cand_p):
            found_md = cand_p
            break

    if not found_md:
        other_mds = [
            f for f in os.listdir(test_dir)
            if f.lower().endswith(('.md', '.txt')) and f.lower() not in [
                'prompt_local_agent.txt',
                'prompt_local_agent_enhanced.txt',
                'prompt_web_ai.txt',
                'prompt_web_ai_enhanced.txt',
                'readme.md',
                'raw_text.md'
            ]
        ]
        if other_mds:
            found_md = os.path.join(test_dir, other_mds[0])

    if found_md and os.path.exists(found_md):
        should_parse_md = (not os.path.exists(q_final))
        if not should_parse_md:
            try:
                should_parse_md = os.path.getmtime(found_md) >= os.path.getmtime(q_final)
            except Exception:
                should_parse_md = False

        if should_parse_md:
            print(f"  {C_CYAN}[i] Parsing {os.path.basename(found_md)} -> questions.json...{C_RESET}")
            img_dir = os.path.join(test_dir, 'images')
            page_map = os.path.join(test_dir, 'page_map.json')
            run_script('5_parse_questions_md.py', [found_md, '-o', q_final, '--image-dir', img_dir, '--page-map', page_map])

    # Auto-detect any candidate JSON file
    if not os.path.exists(q_final):
        candidates = ['final_questions.json', 'output.json', 'response.json', 'data.json', 'interactive_quiz.json']
        for cand in candidates:
            cand_p = os.path.join(test_dir, cand)
            if os.path.exists(cand_p):
                shutil.move(cand_p, q_final)
                break

    if os.path.exists(q_final):
        print(f"  {C_CYAN}[i] Merging answers & running QA checks...{C_RESET}")
        run_script('6_merge_json_answers.py', [test_dir])
        run_script('7_check_json.py', [q_final])
        run_script('8_generate_manifest.py', [])
        cleanup_workspace_folder(test_dir)

        if auto_build:
            print(f"  {C_GREEN}[✔] Compiling standalone HTML quiz...{C_RESET}")
            run_script('9_build_single_html.py', [test_dir])
    else:
        print(f"  {C_GRAY}[i] questions.json pending for {test_name}. Ready for prompt copy-paste.{C_RESET}")


# =========================================================================
# Batch Pipeline & Flag Actions
# =========================================================================

def run_batch_pipeline(target_dir, agent_choice=None, auto_confirm=False, build_only=False, output_dir=None):
    """
    Main entry point for batch processing a folder or tests/ directory.
    """
    print_header()
    check_prerequisites()

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # 1. Scan and group
    tests_dir = os.path.join(CLI_ROOT, 'tests')
    workspaces = scan_and_group_inputs(target_dir, tests_dir)
    if not workspaces:
        print(f"  {C_YELLOW}[!] No exam workspaces or files found in: {target_dir}{C_RESET}")
        print(f"      Drop .pdf or .docx files into '{target_dir}' and run again.\n")
        return

    workspaces_info = [analyze_workspace(w) for w in workspaces]
    agent_found = detect_cli_agent() if agent_choice in [None, 'auto'] else agent_choice
    conv_name, _ = detect_docx_converter()

    # 2. Display 1-Screen Summary Table
    display_batch_summary(workspaces_info, agent_found, conv_name)

    # 3. Confirm proceed
    if not auto_confirm and sys.stdin.isatty():
        choice = input(f"   {C_BOLD}[?] Proceed with batch processing? (Y/n) [Default: Y]: {C_RESET}").strip().lower()
        if choice == 'n':
            print(f"\n{C_CYAN}Batch cancelled by user.{C_RESET}\n")
            return

    print(f"\n{C_CYAN}{'═' * 74}{C_RESET}")
    print(f"{C_BOLD}🚀 Starting Batch Pipeline for {len(workspaces_info)} Exams...{C_RESET}")
    print(f"{C_CYAN}{'═' * 74}{C_RESET}")

    built_quizzes = []
    for info in workspaces_info:
        if build_only:
            # Build ready only
            if info['has_questions_json'] or info['has_questions_md']:
                run_step6(info['name'], info['dir'], os.path.join(info['dir'], 'questions.json'), auto_build=True)
        else:
            process_workspace_auto(info['dir'], agent_choice=agent_choice, auto_confirm=True)

        # Collect compiled HTML files
        html_files = [f for f in os.listdir(info['dir']) if f.lower().endswith('.html')]
        if html_files:
            src_html = os.path.join(info['dir'], html_files[0])
            dst_html = os.path.join(output_dir, f"{info['name']}.html")
            try:
                shutil.copy2(src_html, dst_html)
            except Exception:
                pass

            # Read question count
            q_count = 0
            q_file = os.path.join(info['dir'], 'questions.json')
            if os.path.isfile(q_file):
                try:
                    with open(q_file, 'r', encoding='utf-8') as qf:
                        q_count = len(json.load(qf))
                except Exception:
                    pass

            built_quizzes.append({
                'name': info['name'],
                'title': info['name'].replace('_', ' ').title(),
                'question_count': q_count,
                'html_name': f"{info['name']}.html",
                'path': dst_html,
            })

    # Generate Master Batch Prompts Index
    try:
        from python_scripts.generate_prompts import generate_batch_prompts_index
        batch_md = os.path.join(output_dir, 'BATCH_PROMPTS_INDEX.md')
        generate_batch_prompts_index(workspaces_info, batch_md)
    except Exception:
        pass

    # Generate Master Portal
    portal_path = generate_master_portal(output_dir, built_quizzes)

    print(f"\n{C_GREEN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_GREEN}│{C_RESET} {C_BOLD}{C_WHITE}🎉 BATCH COMPLETE: {len(built_quizzes)} / {len(workspaces_info)} Quizzes Compiled Successfully!{C_RESET}          {C_GREEN}│{C_RESET}")
    print(f"{C_GREEN}├──────────────────────────────────────────────────────────────────────────┤{C_RESET}")
    print(f"{C_GREEN}│{C_RESET}  📁 Output Directory:    {output_dir:<49} {C_GREEN}│{C_RESET}")
    print(f"{C_GREEN}│{C_RESET}  🌐 Master Quiz Portal:  {portal_path:<49} {C_GREEN}│{C_RESET}")
    print(f"{C_GREEN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")

    if sys.stdin.isatty() and not auto_confirm:
        open_choice = input("   [?] Open Master Portal in browser? (Y/n) [Default: Y]: ").strip().lower()
        if open_choice != 'n':
            webbrowser.open(portal_path)


def watch_workspaces(target_dir, output_dir=None):
    """Watch target directory for changes to questions.md or questions.json and auto-rebuild."""
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    tests_dir = os.path.join(CLI_ROOT, 'tests')
    print(f"\n{C_CYAN}[i] 👁️  Watch Mode Active! Monitoring workspaces in {tests_dir}...{C_RESET}")
    print(f"      Save any questions.md or questions.json to trigger instant re-compilation.")
    print(f"      Press Ctrl+C to stop.\n")

    mtimes = {}
    try:
        while True:
            workspaces = [os.path.join(tests_dir, d) for d in os.listdir(tests_dir) if os.path.isdir(os.path.join(tests_dir, d))]
            for w in workspaces:
                for target_file in ['questions.md', 'questions.json']:
                    fp = os.path.join(w, target_file)
                    if os.path.isfile(fp):
                        mtime = os.path.getmtime(fp)
                        if fp in mtimes and mtime > mtimes[fp]:
                            print(f"\n  {C_CYAN}[⚡] Change detected in {os.path.basename(w)}/{target_file}! Rebuilding...{C_RESET}")
                            run_step6(os.path.basename(w), w, os.path.join(w, 'questions.json'), auto_build=True)
                            # Copy to output
                            html_files = [f for f in os.listdir(w) if f.lower().endswith('.html')]
                            if html_files:
                                shutil.copy2(os.path.join(w, html_files[0]), os.path.join(output_dir, f"{os.path.basename(w)}.html"))
                                print(f"  {C_GREEN}[✔] Updated quiz: {output_dir}/{os.path.basename(w)}.html{C_RESET}")
                        mtimes[fp] = mtime
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")


def check_prerequisites():
    print(f" {C_BOLD}[Step 1/6] System Environment Check{C_RESET}")
    print(f" {C_GRAY}{'─' * 74}{C_RESET}")

    missing = []
    if fitz is None:
        missing.append("pymupdf")
    if pd is None:
        missing.append("pandas")

    if missing:
        print(f"  {C_YELLOW}[!] Notice: Optional libraries missing ({', '.join(missing)}).{C_RESET}")
        print(f"      PDF/Excel fallback scripts will run via system handlers if needed.\n")
    else:
        print(f"  {C_GREEN}[✔] Python Core Environment & Libraries are ready.{C_RESET}\n")


def start_local_server(port=8000):
    web_dir = os.path.join(MEI_DIR, 'web')
    if not os.path.isdir(web_dir):
        web_dir = os.path.join(CLI_ROOT, 'web')
    if not os.path.isdir(web_dir):
        web_dir = CLI_ROOT

    os.chdir(web_dir)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    print(f"\n  {C_GREEN}[✔] Local Web Server active at http://localhost:{port}/{C_RESET}")
    print(f"      Opening default browser...\n")

    def serve():
        httpd.serve_forever()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(0.5)
    target_url = f"http://localhost:{port}/index.html" if os.path.isfile(os.path.join(web_dir, 'index.html')) else f"http://localhost:{port}/"
    webbrowser.open(target_url)


def process_workspace(test_name, test_dir):
    """Legacy interactive single-workspace handler for backward compatibility."""
    return process_workspace_auto(test_dir, agent_choice='auto', auto_confirm=False)


def interactive_wizard():
    """Main interactive wizard routing to batch runner or server."""
    run_batch_pipeline(TESTS_DIR, auto_confirm=False)


# =========================================================================
# Main CLI Entry Point
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Modernized Batch Interactive Hebrew Quiz Builder")
    parser.add_argument("folder", nargs="?", default=None, help="Target folder containing exam files or subdirectories (default: ./tests)")
    parser.add_argument("--gui", "-g", action="store_true", help="Launch the modern Desktop GUI Application")
    parser.add_argument("--build", "-b", action="store_true", help="Quick-build all ready workspaces without re-extracting")
    parser.add_argument("--watch", "-w", action="store_true", help="Live watch mode: auto-compile quizzes on questions.md/json save")
    parser.add_argument("--agent", "-a", default=None, help="CLI Agent to use (agy, gemini, claude, none, auto)")
    parser.add_argument("--yes", "-y", action="store_true", help="Non-interactive mode (auto-proceed with batch)")
    parser.add_argument("--output", "-o", default=None, help="Output folder for compiled quizzes (default: ./output)")
    parser.add_argument("--server", "-s", action="store_true", help="Start local web server immediately")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port for local web server")

    args = parser.parse_args()

    target_dir = args.folder or TESTS_DIR

    if args.gui:
        try:
            import tkinter as tk
            from quiz_builder_gui import QuizBuilderGUI
            root = tk.Tk()
            app = QuizBuilderGUI(root, initial_dir=target_dir)
            root.mainloop()
            return
        except Exception as e:
            print(f"Error launching GUI: {e}. Running CLI...")

    if args.server:
        start_local_server(args.port)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nServer stopped.")
        return

    if args.watch:
        watch_workspaces(target_dir, output_dir=args.output)
    else:
        run_batch_pipeline(
            target_dir,
            agent_choice=args.agent,
            auto_confirm=args.yes or not sys.stdin.isatty(),
            build_only=args.build,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
