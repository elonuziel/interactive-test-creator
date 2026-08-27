from __future__ import annotations

from pathlib import Path
import http.server
import os
import socketserver
import subprocess
import sys
import webbrowser


def open_path(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except (OSError, AttributeError):
        return False


def serve(directory: Path, port: int = 8000, open_browser: bool = True) -> None:
    old_cwd = Path.cwd()
    os.chdir(directory)
    try:
        with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as server:
            url = f"http://localhost:{port}/index.html"
            print(f"Serving {directory} at {url}")
            if open_browser:
                webbrowser.open(url)
            server.serve_forever()
    finally:
        os.chdir(old_cwd)
