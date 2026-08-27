@echo off
setlocal
cd /d "%~dp0"
title JARVIS AI OMEGA - Desktop Agent
if not exist ".venv\Scripts\python.exe" (
  echo JARVIS environment not found. Run setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist ".env" (
  echo .env not found. Run setup_windows.ps1, then configure your AI provider credentials.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" desktop_app.py
if errorlevel 1 pause
