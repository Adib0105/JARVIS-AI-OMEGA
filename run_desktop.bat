@echo off
setlocal
cd /d "%~dp0"
title JARVIS AI OMEGA V7 - ARC Desktop Agent
if not exist ".venv\Scripts\python.exe" (
  echo JARVIS environment not found. Run setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist ".env" echo No .env found. Open AI Connection inside JARVIS to set up cloud chat.
".venv\Scripts\python.exe" desktop_app.py
if errorlevel 1 pause
