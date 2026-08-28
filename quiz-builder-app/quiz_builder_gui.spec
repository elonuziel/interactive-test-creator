# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None
spec_dir = SPECPATH
scripts_dir = os.path.join(spec_dir, "python_scripts")
web_dir = os.path.join(spec_dir, "web")
assets_dir = os.path.join(spec_dir, "assets")
src_dir = os.path.join(spec_dir, "src")
icon_file = os.path.join(assets_dir, "app_icon.ico")

datas = [
    (scripts_dir, "python_scripts"),
    (web_dir, "web"),
    (assets_dir, "assets"),
]

a = Analysis(
    [os.path.join(spec_dir, "gui_entry.py")],
    pathex=[spec_dir, src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "fitz",
        "pandas",
        "openpyxl",
        "runpy",
        "quizbuilder.markdown",
        "quizbuilder.gui.dialogs",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="quiz_builder_gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon_file if os.path.exists(icon_file) else None,
)
