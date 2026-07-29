@echo off
cd /d "%~dp0\.."
python python_scripts\8_generate_manifest.py
start http://localhost:8000/web/index.html
python -m http.server 8000
