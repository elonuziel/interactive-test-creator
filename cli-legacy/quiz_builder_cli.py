#!/usr/bin/env python3
"""
quiz_builder_cli.py — Complete Interactive Hebrew Quiz Builder & Local Server
100% faithful Python port of start.bat featuring all wizard steps, AI prompt helpers,
clipboard integration, script pipelines, QA validation, and single-file HTML exporter.
"""

import os
import sys
import json
import re
import glob
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

# ANSI colors for terminal
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_RED = "\033[31m"
C_GRAY = "\033[90m"

# Path setup: Resolve actual directory where the .exe or script is executed
if getattr(sys, 'frozen', False):
    REPO_ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'cli-legacy' else BASE_DIR

TESTS_DIR = os.path.join(REPO_ROOT, 'tests')
PYTHON_SCRIPTS_DIR = os.path.join(REPO_ROOT, 'cli-legacy', 'python_scripts')
if not os.path.isdir(PYTHON_SCRIPTS_DIR):
    PYTHON_SCRIPTS_DIR = os.path.join(REPO_ROOT, 'python_scripts')

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
    print(f"\n{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}  INTERACTIVE HEBREW QUIZ BUILDER (EXECUTABLE WIZARD){C_RESET}")
    print(f"{C_GRAY}  Transform PDF Exams into Interactive Quizzes — 100% Offline Compatible{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"  {C_YELLOW}[!] TIP: Move quiz_builder.exe to whichever folder you want your tests stored in.{C_RESET}")
    print(f"  {C_GRAY}    Current Test Location: {TESTS_DIR}{C_RESET}\n")

def check_prerequisites():
    print(f" {C_BOLD}[Step 1/6] Checking Prerequisites...{C_RESET}")
    print(f" {C_GRAY}{'-' * 75}{C_RESET}")
    
    missing = []
    if fitz is None:
        missing.append("pymupdf")
    if pd is None:
        missing.append("pandas")
        
    if missing:
        print(f"  {C_YELLOW}[!] Notice: Optional Python libraries missing ({', '.join(missing)}).{C_RESET}")
        print(f"      PDF/Excel fallback scripts will run via system handlers if needed.\n")
    else:
        print(f"  {C_GREEN}[OK]{C_RESET} Python Environment & Libraries (PyMuPDF, Pandas) are ready.\n")

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def run_script(script_name, args):
    script_path = os.path.join(PYTHON_SCRIPTS_DIR, script_name)
    if not os.path.isfile(script_path):
        # Fallback search
        script_path = os.path.join(REPO_ROOT, script_name)
    
    cmd = [sys.executable, script_path] + args
    res = subprocess.run(cmd)
    return res.returncode

def start_local_server(port=8000):
    os.chdir(REPO_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    print(f"\n  {C_GREEN}[OK] Local Web Server active at http://localhost:{port}/{C_RESET}")
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
        print(f" {C_BOLD}[Step 2/6] Test Workspace Setup{C_RESET}")
        print(f" {C_GRAY}{'-' * 75}{C_RESET}\n")

        workspaces = [d for d in sorted(os.listdir(TESTS_DIR)) if os.path.isdir(os.path.join(TESTS_DIR, d))]
        has_ready = False
        
        if workspaces:
            print("  Available Test Workspaces:")
            for idx, w in enumerate(workspaces, 1):
                q_path = os.path.join(TESTS_DIR, w, 'questions.json')
                if os.path.exists(q_path):
                    has_ready = True
                    print(f"    [{idx}] {w}  {C_GREEN}[OK READY - questions.json present]{C_RESET}")
                else:
                    print(f"    [{idx}] {w}  {C_YELLOW}[... PENDING - needs processing]{C_RESET}")
        else:
            print("    (No existing test folders found in tests/)")

        print("\n  What would you like to do?")
        if workspaces:
            print(f"    [1-{len(workspaces)}] Select an existing test workspace above")
        print("    [N] Create a NEW test workspace")
        if has_ready:
            print("    [B] BUILD a standalone HTML quiz from a ready test")
            print("    [S] START the local web server to browse tests")
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
            name = input("   [?] Test workspace name [Default: test_1]: ").strip()
            if not name:
                name = "test_1"
            name = name.replace(' ', '_')
            test_dir = os.path.join(TESTS_DIR, name)
            os.makedirs(test_dir, exist_ok=True)
            print(f"\n  {C_GREEN}[OK] Workspace directory created: {test_dir}{C_RESET}\n")
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

def process_workspace(test_name, test_dir):
    # Step 3: Check for source files
    pdf_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
    csv_files = [f for f in os.listdir(test_dir) if f.lower().endswith(('.csv', '.xlsx', '.xls'))]

    if not pdf_files:
        print(f"\n{C_YELLOW}{C_BOLD}{'=' * 75}{C_RESET}")
        print(f"{C_YELLOW}{C_BOLD}                     ACTION REQUIRED: PLACE EXAM FILES{C_RESET}")
        print(f"{C_YELLOW}{C_BOLD}{'=' * 75}{C_RESET}\n")
        print(f"  Please place your exam source files into: {C_BOLD}{test_dir}{C_RESET}")
        print("  Opening workspace folder in Explorer...\n")
        print("  Required files:")
        print("    1. exam.pdf    - Your exam PDF file")
        print("    2. answers.csv - Answer key (CSV or Excel .xlsx / .xls) [Optional]\n")
        print("  Press Enter after copying your files to continue.")
        print(f"{C_YELLOW}{C_BOLD}{'=' * 75}{C_RESET}\n")

        open_in_explorer(test_dir)
        input()

        pdf_files = [f for f in os.listdir(test_dir) if f.lower().endswith('.pdf')]
        csv_files = [f for f in os.listdir(test_dir) if f.lower().endswith(('.csv', '.xlsx', '.xls'))]

    if pdf_files:
        print(f"  {C_GREEN}[OK] PDF File Found: {pdf_files[0]}{C_RESET}")
    else:
        print(f"  {C_YELLOW}[!] WARNING: No PDF file found in {test_dir}{C_RESET}")

    if csv_files:
        print(f"  {C_GREEN}[OK] Answer Key Found: {csv_files[0]}{C_RESET}")
    else:
        print(f"  {C_CYAN}[i] NOTE: No answer key spreadsheet found.{C_RESET}")

    print(f"\n {C_BOLD}[Step 4/6] Document Pre-processing & Analysis{C_RESET}")
    print(f" {C_GRAY}{'-' * 75}{C_RESET}\n")

    # PDF Type Detection
    is_digital = False
    if pdf_files:
        pdf_path = os.path.join(test_dir, pdf_files[0])
        print("  [1/2] Analyzing PDF format (Digital vs Scanned)...")
        res_file = os.path.join(test_dir, 'pdf_type_result.txt')
        run_script('1_detect_pdf_type.py', [pdf_path])

    # Answer Key Form Setup
    form_number = "1"
    if csv_files:
        print(f"\n{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
        print(f"{C_CYAN}{C_BOLD}   [2/2] ANSWER KEY FORM SETUP{C_RESET}")
        print("   Enter the Form Number corresponding to this answer key.")
        print("   (e.g., 32, 76, 1, 0). Refer to your PDF title page if unsure.")
        print(f"{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
        fn_input = input("   [?] Form Number [Default: 1]: ").strip()
        if fn_input:
            form_number = fn_input
        print(f"\n  {C_CYAN}[i] Extracting answers for Form {form_number}...{C_RESET}")
        ans_file = os.path.join(test_dir, csv_files[0])
        out_ans = os.path.join(test_dir, 'answers.json')
        run_script('4_extract_csv_answers.py', [ans_file, form_number, '-o', out_ans])
    else:
        print(f"\n{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
        print(f"{C_CYAN}{C_BOLD}   [2/2] FORM NUMBER SETUP (No answer spreadsheet found){C_RESET}")
        print("   Is this Form 0 (Master Exam where option 1/א is always the answer)?")
        print("   - Enter '0' to auto-generate Form Zero answer key")
        print("   - Enter Form Number (e.g., 1, 32) if adding answers manually later")
        print(f"{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
        fn_input = input("   [?] Form Number [Default: 0 for Form Zero]: ").strip()
        if not fn_input:
            form_number = "0"
        else:
            form_number = fn_input
        if form_number == "0":
            print(f"\n  {C_GREEN}[OK] Form 0 selected! Auto-generating baseline answer key...{C_RESET}")
            out_ans = os.path.join(test_dir, 'answers.json')
            run_script('4_extract_csv_answers.py', ['none', '0', '-o', out_ans])

    skip_step3 = input("\n   [?] Press Enter to run page rendering/text extraction, or 's' to skip: ").strip().lower()
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

        raw_md = os.path.join(test_dir, 'raw_text.md')
        img_dir = os.path.join(test_dir, 'images')
        page_map = os.path.join(test_dir, 'page_map.json')
        q_out = os.path.join(test_dir, 'questions.json')

        run_script('2_extract_text_fitz.py', [pdf_path, '-o', raw_md, '--extract-images', img_dir, '--page-map', page_map])
        run_script('5_parse_questions_md.py', [raw_md, '-o', q_out, '--image-dir', img_dir, '--page-map', page_map])

    # Step 5: AI Agent & Prompt Assistant
    print(f"\n {C_BOLD}[Step 5/6] AI Agent Question Extraction & Proofreading{C_RESET}")
    print(f" {C_GRAY}{'-' * 75}{C_RESET}\n")

    has_answers_flag = "1" if os.path.isfile(os.path.join(test_dir, 'answers.json')) else "0"
    run_script('generate_prompts.py', [test_dir, test_name, form_number, has_answers_flag])

    local_prompt_path = os.path.join(test_dir, 'prompt_local_agent.txt')
    web_prompt_path = os.path.join(test_dir, 'prompt_web_ai.txt')

    if os.path.isfile(local_prompt_path):
        with open(local_prompt_path, 'r', encoding='utf-8') as f:
            local_prompt_text = f.read()
        copy_to_clipboard(local_prompt_text)
        print(f"  {C_GREEN}[OK] Local prompt has been copied to your Windows Clipboard!{C_RESET}")

    print(f"\n{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}                 AI PROMPT ASSISTANT{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'=' * 75}{C_RESET}\n")
    print(f"  Prompt files generated:")
    print(f"    • Local Prompt: {local_prompt_path}")
    print(f"    • Web AI Prompt: {web_prompt_path}\n")
    print("  Select a prompt helper option:")
    print("    [1] LOCAL AGENT (agy, gemini, claude, Cursor, Antigravity, VS Code)")
    print("        Copies local prompt to clipboard.")
    print("    [2] WEB AI (ChatGPT, Claude.ai, Gemini Web, Google AI Studio)")
    print("        Copies web prompt to clipboard & opens AI website.")
    print("    [3] Print both prompts to console")
    print("    [S] Skip prompt helper\n")

    p_choice = input("   [?] Your choice (1/2/3/S) [Default: 1]: ").strip().lower()
    if p_choice == '2':
        if os.path.isfile(web_prompt_path):
            with open(web_prompt_path, 'r', encoding='utf-8') as f:
                copy_to_clipboard(f.read())
            print(f"\n  {C_GREEN}[OK] Web AI prompt copied to clipboard!{C_RESET}\n")
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
        if os.path.isfile(local_prompt_path):
            with open(local_prompt_path, 'r', encoding='utf-8') as f:
                print(f"\n{C_GRAY}--- LOCAL PROMPT ---{C_RESET}\n{f.read()}\n")
        if os.path.isfile(web_prompt_path):
            with open(web_prompt_path, 'r', encoding='utf-8') as f:
                print(f"\n{C_GRAY}--- WEB PROMPT ---{C_RESET}\n{f.read()}\n")

    # Check for candidate JSON files
    q_final = os.path.join(test_dir, 'questions.json')
    if not os.path.exists(q_final):
        candidates = ['final_questions.json', 'output.json', 'response.json', 'data.json']
        for cand in candidates:
            cand_p = os.path.join(test_dir, cand)
            if os.path.exists(cand_p):
                print(f"\n  {C_CYAN}[i] Found {cand}. Renaming to questions.json...{C_RESET}")
                shutil.move(cand_p, q_final)
                break

    # Step 6: Post-processing & Validation
    print(f"\n {C_BOLD}[Step 6/6] Automated Post-Processing & Validation{C_RESET}")
    print(f" {C_GRAY}{'-' * 75}{C_RESET}\n")

    if os.path.exists(q_final):
        print(f"  {C_CYAN}[i] Merging answer key into questions.json...{C_RESET}")
        run_script('6_merge_json_answers.py', [test_dir])

        print(f"\n  {C_CYAN}[i] Running QA schema validation...{C_RESET}")
        run_script('7_check_json.py', [q_final])

        print(f"\n  {C_CYAN}[i] Updating test manifest...{C_RESET}")
        run_script('8_generate_manifest.py', [])

        print(f"\n  {C_GREEN}[OK] All processing steps finished!{C_RESET}\n")
        build_opt = input("   [?] Build standalone HTML quiz now? (Y/n) [Default: Y]: ").strip().lower()
        if build_opt != 'n':
            run_script('9_build_single_html.py', [test_dir])
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
