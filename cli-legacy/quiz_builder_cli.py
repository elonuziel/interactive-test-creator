#!/usr/bin/env python3
"""
quiz_builder_cli.py — Complete Interactive Hebrew Quiz Builder & Local Server
100% faithful Python port of start.bat featuring in-process script execution,
AI agent auto-launchers, Explorer folder opening, ANSI VT colors, and standalone HTML exporting.
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
    REPO_ROOT = os.path.dirname(os.path.abspath(sys.executable))
    MEI_DIR = getattr(sys, '_MEIPASS', REPO_ROOT)
    PYTHON_SCRIPTS_DIR = os.path.join(MEI_DIR, 'python_scripts')
    if not os.path.isdir(PYTHON_SCRIPTS_DIR):
        PYTHON_SCRIPTS_DIR = os.path.join(MEI_DIR, 'cli-legacy', 'python_scripts')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'cli-legacy' else BASE_DIR
    MEI_DIR = BASE_DIR
    PYTHON_SCRIPTS_DIR = os.path.join(REPO_ROOT, 'cli-legacy', 'python_scripts')
    if not os.path.isdir(PYTHON_SCRIPTS_DIR):
        PYTHON_SCRIPTS_DIR = os.path.join(REPO_ROOT, 'python_scripts')

TESTS_DIR = os.path.join(REPO_ROOT, 'tests')

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

def print_header():
    print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_BOLD}{C_WHITE}         INTERACTIVE HEBREW QUIZ BUILDER (CLI EXECUTABLE)                 {C_RESET} {C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}│{C_RESET} {C_GRAY}  Transform PDF Exams & Spreadsheet Answer Keys into Interactive Quizzes  {C_RESET} {C_CYAN}│{C_RESET}")
    print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
    print(f"  {C_YELLOW}💡 TIP: Move quiz_builder.exe to any folder to manage your tests there.{C_RESET}")
    print(f"  {C_GRAY}   Current Storage Location: {TESTS_DIR}{C_RESET}\n")

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

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def run_script(script_name, args):
    """Run a pipeline script in-process to guarantee PyInstaller compatibility."""
    candidate_paths = [
        os.path.join(PYTHON_SCRIPTS_DIR, script_name),
        os.path.join(MEI_DIR, 'python_scripts', script_name),
        os.path.join(MEI_DIR, 'cli-legacy', 'python_scripts', script_name),
        os.path.join(REPO_ROOT, 'cli-legacy', 'python_scripts', script_name),
        os.path.join(REPO_ROOT, 'python_scripts', script_name),
        os.path.join(REPO_ROOT, script_name),
    ]

    script_path = None
    for cand in candidate_paths:
        if os.path.isfile(cand):
            script_path = cand
            break

    if not script_path:
        print(f"  {C_RED}[✘] Error: Script {script_name} not found in bundle or disk.{C_RESET}")
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

def start_local_server(port=8000):
    os.chdir(REPO_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    print(f"\n  {C_GREEN}[✔] Local Web Server active at http://localhost:{port}/{C_RESET}")
    print(f"      Opening default browser...\n")
    
    def serve():
        httpd.serve_forever()
        
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    
    time.sleep(0.5)
    target_url = f"http://localhost:{port}/quiz_generator.html" if os.path.isfile(os.path.join(REPO_ROOT, 'quiz_generator.html')) else f"http://localhost:{port}/"
    webbrowser.open(target_url)

def interactive_wizard():
    print_header()
    check_prerequisites()

    os.makedirs(TESTS_DIR, exist_ok=True)

    while True:
        print(f" {C_BOLD}[Step 2/6] Test Workspaces{C_RESET}")
        print(f" {C_GRAY}{'─' * 74}{C_RESET}\n")

        workspaces = [d for d in sorted(os.listdir(TESTS_DIR)) if os.path.isdir(os.path.join(TESTS_DIR, d))]
        has_ready = False
        
        if workspaces:
            print("  Available Workspaces:")
            for idx, w in enumerate(workspaces, 1):
                w_path = os.path.join(TESTS_DIR, w)
                q_path = os.path.join(w_path, 'questions.json')
                html_files = [f for f in os.listdir(w_path) if f.endswith('.html')]
                
                if os.path.exists(q_path):
                    has_ready = True
                    status_badge = f"{C_GREEN}[READY]{C_RESET}"
                    extra_info = f" ({len(html_files)} HTML built)" if html_files else ""
                else:
                    status_badge = f"{C_YELLOW}[PENDING]{C_RESET}"
                    extra_info = ""
                print(f"    [{idx}] {w:<20} {status_badge}{extra_info}")
        else:
            print("    (No existing test folders found in tests/)")

        print("\n  Actions:")
        if workspaces:
            print(f"    [1-{len(workspaces)}] Select an existing test workspace")
        print("    [N] Create a NEW test workspace")
        if has_ready:
            print("    [B] Build standalone HTML quiz from ready test")
            print("    [S] Start local web server to browse quizzes")
        print("    [Q] Quit\n")

        choice = input("   [?] Your choice: ").strip()
        if not choice:
            continue

        if choice.lower() == 'q':
            print(f"\n{C_CYAN}Exiting Quiz Builder. Goodbye!{C_RESET}\n")
            break
        elif choice.lower() == 's':
            start_local_server(8000)
            input("   Press Enter to stop the web server and return to menu...")
            continue
        elif choice.lower() == 'n':
            name = input("   [?] Test workspace name (e.g. 9900, bio_101) [Default: test_1]: ").strip()
            if not name:
                name = "test_1"
            name = name.replace(' ', '_')
            test_dir = os.path.join(TESTS_DIR, name)
            os.makedirs(test_dir, exist_ok=True)
            print(f"\n  {C_GREEN}[✔] Workspace directory created: {test_dir}{C_RESET}\n")
            process_workspace(name, test_dir)
        elif choice.lower() == 'b':
            if not workspaces:
                print(f"\n  {C_YELLOW}[!] No test workspaces found.{C_RESET}\n")
                continue
            print("\n  Select workspace to build:")
            for idx, w in enumerate(workspaces, 1):
                print(f"    [{idx}] {w}")
            w_idx = input("   [?] Workspace number: ").strip()
            if w_idx.isdigit() and 1 <= int(w_idx) <= len(workspaces):
                target = workspaces[int(w_idx) - 1]
                run_script('9_build_single_html.py', [os.path.join(TESTS_DIR, target)])
        elif choice.isdigit() and 1 <= int(choice) <= len(workspaces):
            target = workspaces[int(choice) - 1]
            test_dir = os.path.join(TESTS_DIR, target)
            print(f"\n  Workspace Selected: {C_BOLD}{target}{C_RESET}")
            q_file = os.path.join(test_dir, 'questions.json')
            if os.path.exists(q_file):
                print(f"  Status: {C_GREEN}READY (questions.json present){C_RESET}\n")
                print(f"  Select an action for {target}:")
                print("    [1] Build standalone HTML quiz file")
                print("    [2] Re-process with AI agent (re-extract / proofread)")
                print("    [B] Back to main menu\n")
                ex_choice = input("   [?] Your choice (1/2/B) [Default: 1]: ").strip().lower()
                if ex_choice == '2':
                    process_workspace(target, test_dir)
                elif ex_choice == 'b':
                    continue
                else:
                    run_script('9_build_single_html.py', [test_dir])
            else:
                print(f"  Status: {C_YELLOW}PENDING (requires processing){C_RESET}\n")
                process_workspace(target, test_dir)

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

def cleanup_workspace_folder(test_dir):
    """Clean up scratch files, prompt txt files, clean merged PDFs, and unused page renders."""
    scratch_files = [
        'raw_text.md',
        'pdf_type_result.txt',
        'page_map.json',
        'prompt_local_agent.txt',
        'prompt_web_ai.txt',
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

    # Delete any clean merged PDFs (*_clean.pdf) and any leftover prompt .txt files
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

        # If no page images were referenced and folder is now empty, remove folder
        if kept_pages == 0 and len(os.listdir(pages_dir)) == 0:
            try:
                os.rmdir(pages_dir)
            except Exception:
                pass
        else:
            print(f"  {C_GRAY}[i] Preserved {kept_pages} diagram/table image(s) in pages_output/{C_RESET}")

    if cleaned > 0 or deleted_pages > 0:
        print(f"  {C_GRAY}[i] Workspace Cleanup: Removed {cleaned} scratch file(s) and {deleted_pages} unused page render(s).{C_RESET}")

def process_workspace(test_name, test_dir):
    # Step 3: Check for source files & launch Explorer
    pdf_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
    csv_files = [f for f in os.listdir(test_dir) if f.lower().endswith(('.csv', '.xlsx', '.xls'))]

    if not pdf_files:
        print(f"\n{C_YELLOW}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"{C_YELLOW}│                   ACTION REQUIRED: PLACE EXAM FILES                      │{C_RESET}")
        print(f"{C_YELLOW}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")
        print(f"  Please place your exam source files into workspace:")
        print(f"  📁 {C_BOLD}{test_dir}{C_RESET}\n")
        print("  Required files:")
        print("    1. exam.pdf    - Your exam PDF file")
        print("    2. answers.csv - Answer key (CSV or Excel .xlsx / .xls) [Optional]\n")
        print("  Opening workspace folder in Explorer...")
        open_in_explorer(test_dir)
        input("  Press Enter after copying your files into the workspace folder...")

        pdf_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
        csv_files = [f for f in os.listdir(test_dir) if f.lower().endswith(('.csv', '.xlsx', '.xls'))]

    if pdf_files:
        print(f"  {C_GREEN}[✔] PDF File Found: {pdf_files[0]}{C_RESET}")
    else:
        print(f"  {C_YELLOW}[!] WARNING: No PDF file found in {test_dir}{C_RESET}")

    if csv_files:
        print(f"  {C_GREEN}[✔] Answer Key Found: {csv_files[0]}{C_RESET}")
    else:
        print(f"  {C_CYAN}[i] NOTE: No answer key spreadsheet found.{C_RESET}")

    print(f"\n {C_BOLD}[Step 4/6] Document Pre-processing & Format Analysis{C_RESET}")
    print(f" {C_GRAY}{'─' * 74}{C_RESET}\n")

    # PDF Type Detection
    is_digital = False
    if pdf_files:
        pdf_path = os.path.join(test_dir, pdf_files[0])
        print("  [1/2] Analyzing PDF format (Digital vs Scanned)...")
        run_script('1_detect_pdf_type.py', [pdf_path])
        is_digital = is_pdf_digital(pdf_path)

    # Answer Key Form Setup
    form_number = "1"
    if csv_files:
        print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"{C_CYAN}│ [2/2] ANSWER KEY FORM SETUP                                              │{C_RESET}")
        print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
        print("   Enter the Form Number corresponding to this answer key.")
        print("   (e.g., 111, 32, 76, 1, 0). Refer to your PDF title page if unsure.\n")
        fn_input = input("   [?] Form Number [Default: 1]: ").strip()
        if fn_input:
            form_number = fn_input
        print(f"\n  {C_CYAN}[i] Extracting answer key for Form {form_number}...{C_RESET}")
        ans_file = os.path.join(test_dir, csv_files[0])
        out_ans = os.path.join(test_dir, 'answers.json')
        run_script('4_extract_csv_answers.py', [ans_file, form_number, '-o', out_ans])
    else:
        print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"{C_CYAN}│ [2/2] FORM NUMBER SETUP (No answer spreadsheet found)                   │{C_RESET}")
        print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
        print("   Is this Form 0 (Master Exam where option 1/א is always the answer)?")
        print("   • Enter '0' to auto-generate Form Zero answer key")
        print("   • Enter Form Number (e.g., 111, 32, 1) if adding answers manually later\n")
        fn_input = input("   [?] Form Number [Default: 0 for Form Zero]: ").strip()
        if not fn_input:
            form_number = "0"
        else:
            form_number = fn_input
        if form_number == "0":
            print(f"\n  {C_GREEN}[✔] Form 0 selected! Auto-generating baseline answer key...{C_RESET}")
            out_ans = os.path.join(test_dir, 'answers.json')
            run_script('4_extract_csv_answers.py', ['none', '0', '-o', out_ans])

    skip_step3 = input("\n   [?] Press Enter to run page rendering & text extraction, or 's' to skip: ").strip().lower()
    if skip_step3 != 's' and pdf_files:
        pdf_path = os.path.join(test_dir, pdf_files[0])
        print("\n  Page Cleaning Options:")
        print("    • Press [Enter] for Standard cleaning (skips cover/instructions pages 1-4, 6,8,10...)")
        print("    • Type custom pages to discard (e.g., '1-3, 5')")
        print("    • Type 'none' to preserve all pages\n")
        discard_pages = input("   [?] Discard pages [Default: standard]: ").strip()
        if not discard_pages:
            discard_pages = "std"

        print(f"\n  {C_CYAN}[i] Rendering clean PDF pages...{C_RESET}")
        out_pages = os.path.join(test_dir, 'pages_output')
        clean_pdf = os.path.join(test_dir, f"{test_name}_clean.pdf")
        run_script('3_render_pdf_pages.py', [pdf_path, '-o', out_pages, '--discard-pages', discard_pages, '--merged-pdf', clean_pdf])
        
        # Open rendered page output folder in Explorer for visual inspection / AI referencing
        print("  Opening rendered pages output folder in Explorer...\n")
        open_in_explorer(out_pages)

        if is_digital:
            print(f"  {C_GREEN}[✔] DIGITAL PDF DETECTED: Extracting text automatically...{C_RESET}")
            raw_md = os.path.join(test_dir, 'raw_text.md')
            img_dir = os.path.join(test_dir, 'images')
            page_map = os.path.join(test_dir, 'page_map.json')
            q_out = os.path.join(test_dir, 'questions.json')

            run_script('2_extract_text_fitz.py', [pdf_path, '-o', raw_md, '--extract-images', img_dir, '--page-map', page_map])
            run_script('5_parse_questions_md.py', [raw_md, '-o', q_out, '--image-dir', img_dir, '--page-map', page_map])
        else:
            print(f"  {C_YELLOW}[!] SCANNED PDF DETECTED: Skipping PyMuPDF text parsing.{C_RESET}")
            print(f"      Rendered page images are ready in pages_output/ for AI agent extraction.\n")

    # Step 5: AI Agent & Prompt Assistant
    print(f"\n {C_BOLD}[Step 5/6] AI Agent Question Extraction & Proofreading{C_RESET}")
    print(f" {C_GRAY}{'─' * 74}{C_RESET}\n")

    q_exists = os.path.exists(os.path.join(test_dir, 'questions.json'))
    if q_exists:
        print(f"  {C_CYAN}[i] Automated text extraction is complete!{C_RESET}")
        print("      Hebrew text extraction may benefit from an AI proofreading pass to fix reversed words.")
        proof_choice = input("\n   [?] Run AI proofreading pass on questions.json? (Y/n) [Default: Y]: ").strip().lower()
        if proof_choice == 'n':
            print(f"  {C_CYAN}[i] Skipping AI proofreading pass. Proceeding to post-processing...{C_RESET}")
            q_final = os.path.join(test_dir, 'questions.json')
            # Jump directly to Step 6
            run_step6(test_name, test_dir, q_final)
            return
        else:
            print(f"\n  {C_CYAN}[i] Preparing AI proofreading prompt...{C_RESET}")
    else:
        print(f"  {C_CYAN}[i] AI Agent pass needed to extract questions from rendered pages into questions.json.{C_RESET}")

    has_answers_flag = "1" if os.path.isfile(os.path.join(test_dir, 'answers.json')) else "0"
    local_prompt_path = os.path.join(test_dir, 'prompt_local_agent.txt')
    web_prompt_path = os.path.join(test_dir, 'prompt_web_ai.txt')

    # Check CLI Agents
    agent_found = None
    for ag in ['agy', 'gemini', 'claude']:
        if shutil.which(ag):
            agent_found = ag
            break

    if agent_found:
        print(f"  {C_GREEN}[✔] Detected CLI Agent: {agent_found}{C_RESET}")
        use_ag = input(f"   [?] Launch {agent_found} automatically? (Y/n) [Default: Y]: ").strip().lower()
        if use_ag != 'n':
            # Generate local prompt on demand
            run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag, 'local'])
            if os.path.isfile(local_prompt_path):
                print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
                print(f"{C_CYAN}│ LAUNCHING LOCAL AGENT: {agent_found:<49} │{C_RESET}")
                print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
                print("   1. Opening agent in a new terminal window with prompt piped.")
                print("   2. The agent will output/update questions.json automatically.")
                print("   3. Once finished, return here and press Enter to continue.\n")
                if sys.platform == 'win32':
                    cmd_str = f'type "{local_prompt_path}" | {agent_found}'
                    subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', cmd_str], shell=True)
                input("   Press Enter after the AI agent completes...")

    mode_title = "PROOFREADING ASSISTANT" if q_exists else "EXTRACTION ASSISTANT"
    print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_CYAN}│ AI {mode_title:<69} │{C_RESET}")
    print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")
    print("  Select a prompt helper option:")
    print("    [1] LOCAL AGENT (agy, gemini, claude, Cursor, Antigravity, VS Code)")
    print("        Generates prompt_local_agent.txt on demand.")
    print("    [2] WEB AI (ChatGPT, Claude.ai, Gemini Web, Google AI Studio)")
    print("        Generates prompt_web_ai.txt on demand & opens AI website.")
    print("    [3] Print both prompts to console")
    print("    [S] Skip prompt helper\n")

    p_choice = input("   [?] Your choice (1/2/3/S) [Default: 1]: ").strip().lower()
    if p_choice == '2':
        run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag, 'web'])
        print(f"\n  {C_GREEN}[✔] Created {web_prompt_path}{C_RESET}")
        print("  Open a Web AI assistant in browser?")
        print("    [1] ChatGPT (chatgpt.com)")
        print("    [2] Gemini Web (gemini.google.com)")
        print("    [3] Claude Web (claude.ai)")
        print("    [4] Google AI Studio (aistudio.google.com)")
        print("    [N] Skip opening browser\n")
        web_choice = input("   [?] Your choice (1/2/3/4/N): ").strip()
        if web_choice == '1': webbrowser.open('https://chatgpt.com')
        elif web_choice == '2': webbrowser.open('https://gemini.google.com')
        elif web_choice == '3': webbrowser.open('https://claude.ai')
        elif web_choice == '4': webbrowser.open('https://aistudio.google.com')
    elif p_choice == '3':
        run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag, 'all'])
        if os.path.isfile(local_prompt_path):
            with open(local_prompt_path, 'r', encoding='utf-8') as f:
                print(f"\n{C_GRAY}--- LOCAL PROMPT ---{C_RESET}\n{f.read()}\n")
        if os.path.isfile(web_prompt_path):
            with open(web_prompt_path, 'r', encoding='utf-8') as f:
                print(f"\n{C_GRAY}--- WEB PROMPT ---{C_RESET}\n{f.read()}\n")
    elif p_choice != 's':
        run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag, 'local'])
        print(f"\n  {C_GREEN}[✔] Created {local_prompt_path}{C_RESET}")

    if p_choice != 's':
        print(f"\n{C_CYAN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"{C_CYAN}│          NEXT STEPS: QUESTION EXTRACTION / PROOFREADING                  │{C_RESET}")
        print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}")
        print("   1. Open the generated prompt file:")
        print(f"      • Local: {local_prompt_path}")
        print(f"      • Web:   {web_prompt_path}")
        print("   2. Copy the prompt text and paste it into your AI assistant.")
        print("   3. (If using Web AI for Scanned PDF) Upload page images from pages_output/.")
        print(f"   4. Save the AI's returned JSON array as 'questions.json' into:")
        print(f"      📁 {test_dir}")
        print("   5. Once 'questions.json' is ready, return here and press Enter.")
        print(f"{C_CYAN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")
        input("   [?] Press Enter when questions.json is ready in test folder...")

    # Check for candidate JSON files
    q_final = os.path.join(test_dir, 'questions.json')
    if not os.path.exists(q_final):
        candidates = ['final_questions.json', 'output.json', 'response.json', 'data.json', 'interactive_quiz.json']
        found = False
        for cand in candidates:
            cand_p = os.path.join(test_dir, cand)
            if os.path.exists(cand_p):
                print(f"\n  {C_CYAN}[i] Found candidate {cand}. Renaming to questions.json...{C_RESET}")
                shutil.move(cand_p, q_final)
                found = True
                break

        if not found:
            other_jsons = [
                f for f in os.listdir(test_dir)
                if f.lower().endswith('.json') and f.lower() not in ['answers.json', 'page_map.json', 'questions.json']
            ]
            if other_jsons:
                target_json = other_jsons[0]
                cand_p = os.path.join(test_dir, target_json)
                print(f"\n  {C_CYAN}[i] Auto-detected question JSON file ({target_json}). Renaming to questions.json...{C_RESET}")
                shutil.move(cand_p, q_final)

    # Step 6: Post-processing & Validation
    run_step6(test_name, test_dir, q_final)

def run_step6(test_name, test_dir, q_final):
    print(f"\n {C_BOLD}[Step 6/6] Automated Post-Processing & Validation{C_RESET}")
    print(f" {C_GRAY}{'─' * 74}{C_RESET}\n")

    if os.path.exists(q_final):
        print(f"  {C_CYAN}[i] Merging answer key into questions.json...{C_RESET}")
        run_script('6_merge_json_answers.py', [test_dir])

        print(f"\n  {C_CYAN}[i] Running QA schema validation...{C_RESET}")
        run_script('7_check_json.py', [q_final])

        print(f"\n  {C_CYAN}[i] Updating test manifest...{C_RESET}")
        run_script('8_generate_manifest.py', [])

        # Clean up intermediate scratch files
        cleanup_workspace_folder(test_dir)

        print(f"\n  {C_GREEN}[✔] All post-processing steps completed successfully!{C_RESET}\n")
        build_opt = input("   [?] Build standalone HTML quiz now? (Y/n) [Default: Y]: ").strip().lower()
        if build_opt != 'n':
            run_script('9_build_single_html.py', [test_dir])
            
            # Find generated HTML file
            html_files = [f for f in os.listdir(test_dir) if f.endswith('.html')]
            html_name = html_files[0] if html_files else f"{test_name}_interactive_quiz.html"
            html_path = os.path.join(test_dir, html_name)

            print(f"\n{C_GREEN}┌──────────────────────────────────────────────────────────────────────────┐{C_RESET}")
            print(f"{C_GREEN}│                       🎉 QUIZ BUILD COMPLETE!                           │{C_RESET}")
            print(f"{C_GREEN}├──────────────────────────────────────────────────────────────────────────┤{C_RESET}")
            print(f"{C_GREEN}│{C_RESET}  📄 Quiz File: {html_name:<57} {C_GREEN}│{C_RESET}")
            print(f"{C_GREEN}│{C_RESET}  📁 Folder:    {test_dir:<57} {C_GREEN}│{C_RESET}")
            print(f"{C_GREEN}└──────────────────────────────────────────────────────────────────────────┘{C_RESET}\n")
            print("  Options:")
            print("    [1] Open HTML quiz in default Web Browser")
            print("    [2] Open test workspace folder in Explorer")
            print("    [M] Return to Main Menu\n")

            post_choice = input("   [?] Your choice (1/2/M) [Default: 1]: ").strip().lower()
            if post_choice == '2':
                open_in_explorer(test_dir)
            elif post_choice != 'm':
                if os.path.exists(html_path):
                    webbrowser.open(html_path)
                else:
                    open_in_explorer(test_dir)
    else:
        print(f"  {C_YELLOW}[!] questions.json not found in {test_dir}. Place questions.json to complete building.{C_RESET}\n")

def main():
    parser = argparse.ArgumentParser(description="Interactive Hebrew Quiz Builder Executable")
    parser.add_argument("--server", action="store_true", help="Start local web server immediately")
    parser.add_argument("--port", type=int, default=8000, help="Port for local web server")
    args = parser.parse_args()

    if args.server:
        start_local_server(args.port)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nServer stopped.")
    else:
        interactive_wizard()

if __name__ == "__main__":
    main()
