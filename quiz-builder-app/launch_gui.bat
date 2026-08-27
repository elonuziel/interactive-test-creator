@echo off
rem Launch the Interactive Hebrew Quiz Builder desktop GUI
set SCRIPT_DIR=%~dp0
set PYTHONPATH=%SCRIPT_DIR%src
python -m quizbuilder.gui %*
