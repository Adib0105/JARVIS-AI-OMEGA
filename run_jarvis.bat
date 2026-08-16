@echo off
setlocal
cd /d "%~dp0"
title JARVIS AI OMEGA V6 - Terminal Agent
if not exist ".venv\Scripts\python.exe" (
  echo JARVIS V6 environment not found. Run setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist ".env" (
  echo .env not found. Run setup_windows.ps1, then configure your AI provider key.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
