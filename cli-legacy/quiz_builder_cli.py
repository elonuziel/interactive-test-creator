#!/usr/bin/env python3
"""
quiz_builder_cli.py — Standalone Interactive Quiz Builder & Local Server
Replicates full start.bat interactive CLI wizard and backend utilities in a single Python executable.
"""

import os
import sys
import json
import re
import mimetypes
import base64
import argparse
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
    # Running inside PyInstaller bundled executable
    REPO_ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'cli-legacy' else BASE_DIR

TESTS_DIR = os.path.join(REPO_ROOT, 'tests')

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
        print(f"  {C_YELLOW}[!] Warning: Missing optional packages: {', '.join(missing)}{C_RESET}")
        print(f"      PDF extraction or XLSX parsing will fall back to built-in handlers.\n")
    else:
        print(f"  {C_GREEN}[OK]{C_RESET} All required Python libraries (PyMuPDF, Pandas) are loaded.\n")

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def detect_pdf_type(pdf_path, sample_pages=3, min_chars=50):
    if fitz is None:
        return "UNKNOWN (PyMuPDF not loaded)"
    try:
        doc = fitz.open(pdf_path)
        total_chars = 0
        pages_checked = min(sample_pages, len(doc))
        if pages_checked == 0:
            return "EMPTY"
        for i in range(pages_checked):
            total_chars += len(doc[i].get_text().strip())
        avg = total_chars / pages_checked
        return "DIGITAL" if avg >= min_chars else "SCANNED"
    except Exception as e:
        return f"ERROR: {e}"

def render_pdf_pages_to_images(pdf_path, output_folder, dpi=150):
    if fitz is None:
        print(f"  {C_RED}[!] PyMuPDF is required to render PDF page images.{C_RESET}")
        return 0
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)
    count = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        out_path = os.path.join(output_folder, f"page_{page_num + 1}.png")
        pix.save(out_path)
        count += 1
    return count

def generate_test_manifest():
    if not os.path.isdir(TESTS_DIR):
        return
    manifest = []
    for item in sorted(os.listdir(TESTS_DIR)):
        item_path = os.path.join(TESTS_DIR, item)
        if os.path.isdir(item_path):
            q_file = os.path.join(item_path, 'questions.json')
            if os.path.isfile(q_file):
                try:
                    with open(q_file, 'r', encoding='utf-8') as f:
                        q_data = json.load(f)
                    manifest.append({
                        "id": item,
                        "title": item.replace('_', ' ').title(),
                        "questionCount": len(q_data),
                        "path": f"tests/{item}/questions.json"
                    })
                except Exception:
                    pass
    manifest_path = os.path.join(TESTS_DIR, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  {C_GREEN}[OK]{C_RESET} Manifest updated: {manifest_path} ({len(manifest)} test(s) cataloged)")

def build_standalone_html(test_dir_name, output_path=None):
    test_dir = os.path.join(TESTS_DIR, test_dir_name) if not os.path.isabs(test_dir_name) else test_dir_name
    questions_file = os.path.join(test_dir, 'questions.json')
    if not os.path.isfile(questions_file):
        print(f"  {C_RED}[!] Error: questions.json not found in {test_dir}{C_RESET}")
        return False

    index_path = os.path.join(REPO_ROOT, 'index.html')
    style_path = os.path.join(REPO_ROOT, 'style.css')
    app_path = os.path.join(REPO_ROOT, 'app.js')

    if not os.path.isfile(index_path):
        print(f"  {C_RED}[!] Error: index.html not found in {REPO_ROOT}{C_RESET}")
        return False

    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()
    with open(style_path, 'r', encoding='utf-8') as f:
        css = f.read()
    with open(app_path, 'r', encoding='utf-8') as f:
        js = f.read()
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    # Embed images as base64 data URIs if present
    img_bytes = 0
    for q in questions:
        if q.get('image'):
            img_rel = q['image']
            img_abs = os.path.join(test_dir, img_rel)
            if os.path.isfile(img_abs):
                mime, _ = mimetypes.guess_type(img_abs)
                mime = mime or 'image/png'
                with open(img_abs, 'rb') as img_f:
                    b64 = base64.b64encode(img_f.read()).decode('ascii')
                q['image'] = f"data:{mime};base64,{b64}"
                img_bytes += os.path.getsize(img_abs)

    inlined_css = f"<style>\n{css}\n</style>"
    html = re.sub(r'<link\s+rel="stylesheet"\s+href="style\.css"\s*/?>', lambda _: inlined_css, html)

    embedded_data = f"<script>window.__INLINE_QUESTIONS__ = {json.dumps(questions, ensure_ascii=False, indent=2)};\n(function(){{const orig=window.fetch.bind(window);window.fetch=function(i,n){{const u=typeof i==='string'?i:(i&&i.url)||'';if(typeof u==='string'&&/questions\\.json(?:\\?|$)/.test(u)){{return Promise.resolve(new Response(JSON.stringify(window.__INLINE_QUESTIONS__),{{headers:{{'Content-Type':'application/json'}}}}));}}return orig(i,n);}};}})();</script>"
    
    inlined_js = f"{embedded_data}\n<script>\n{js}\n</script>"
    html = re.sub(r'<script\s+src="app\.js">\s*</script>', lambda _: inlined_js, html)

    out_file = output_path or os.path.join(REPO_ROOT, f"{os.path.basename(test_dir)}_quiz.html")
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)

    size_str = format_size(os.path.getsize(out_file))
    print(f"\n  {C_GREEN}[OK] Standalone HTML quiz created successfully!{C_RESET}")
    print(f"      File: {C_BOLD}{out_file}{C_RESET}")
    print(f"      Questions: {len(questions)}")
    print(f"      Total Size: {size_str}")
    print(f"      Double-click to open in any web browser 100% offline!\n")
    return True

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
    webbrowser.open(f"http://localhost:{port}/quiz_generator.html")

def interactive_wizard():
    print_header()
    check_prerequisites()

    os.makedirs(TESTS_DIR, exist_ok=True)

    while True:
        print(f" {C_BOLD}[Step 2/6] Test Workspace Menu{C_RESET}")
        print(f" {C_GRAY}{'-' * 75}{C_RESET}")

        workspaces = [d for d in sorted(os.listdir(TESTS_DIR)) if os.path.isdir(os.path.join(TESTS_DIR, d))]
        
        if workspaces:
            print("  Available Test Workspaces:")
            for idx, w in enumerate(workspaces, 1):
                q_path = os.path.join(TESTS_DIR, w, 'questions.json')
                status = f"{C_GREEN}[READY - questions.json present]{C_RESET}" if os.path.exists(q_path) else f"{C_YELLOW}[PENDING]{C_RESET}"
                print(f"    [{idx}] {w} {status}")
        else:
            print("    (No existing test folders in tests/)")

        print("\n  Actions:")
        if workspaces:
            print("    [1-N] Select an existing test workspace")
        print("    [N] Create a NEW test workspace")
        print("    [B] Build standalone HTML quiz from a ready test")
        print("    [S] Start local HTTP Web Server & open builder")
        print("    [Q] Quit\n")

        choice = input("   [?] Your choice: ").strip().lower()

        if choice == 'q':
            print(f"\n{C_CYAN}Exiting Quiz Builder. Goodbye!{C_RESET}\n")
            break
        elif choice == 's':
            start_local_server(8000)
            input("   Press Enter to stop the web server and return to menu...")
        elif choice == 'n':
            name = input("   [?] Enter name for new test workspace: ").strip().replace(' ', '_')
            if name:
                new_dir = os.path.join(TESTS_DIR, name)
                os.makedirs(new_dir, exist_ok=True)
                print(f"\n  {C_GREEN}[OK] Workspace created: {new_dir}{C_RESET}\n")
        elif choice == 'b':
            if not workspaces:
                print(f"\n  {C_YELLOW}[!] No test workspaces found.{C_RESET}\n")
                continue
            print("\n  Select workspace to build:")
            for idx, w in enumerate(workspaces, 1):
                print(f"    [{idx}] {w}")
            w_idx = input("   [?] Workspace number: ").strip()
            if w_idx.isdigit() and 1 <= int(w_idx) <= len(workspaces):
                target = workspaces[int(w_idx) - 1]
                build_standalone_html(target)
        elif choice.isdigit() and 1 <= int(choice) <= len(workspaces):
            target = workspaces[int(choice) - 1]
            target_path = os.path.join(TESTS_DIR, target)
            print(f"\n  Selected: {C_BOLD}{target}{C_RESET}")
            q_file = os.path.join(target_path, 'questions.json')
            if os.path.exists(q_file):
                print(f"  Status: {C_GREEN}READY{C_RESET}")
                sub = input("   [?] [1] Build standalone HTML, [2] Update Manifest, [B] Back: ").strip()
                if sub == '1':
                    build_standalone_html(target)
                elif sub == '2':
                    generate_test_manifest()
            else:
                print(f"  Status: {C_YELLOW}PENDING{C_RESET}")
                print(f"  Drop your PDF or questions.json into: {target_path}")
                pdf_files = [f for f in os.listdir(target_path) if f.lower().endswith('.pdf')]
                if pdf_files:
                    pdf_p = os.path.join(target_path, pdf_files[0])
                    pdf_type = detect_pdf_type(pdf_p)
                    print(f"  Detected PDF: {pdf_files[0]} ({pdf_type})")
                    if fitz:
                        out_imgs = os.path.join(target_path, 'images')
                        rendered = render_pdf_pages_to_images(pdf_p, out_imgs)
                        print(f"  {C_GREEN}[OK] Rendered {rendered} page images to {out_imgs}{C_RESET}")
                input("\n   Press Enter to continue...")

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
