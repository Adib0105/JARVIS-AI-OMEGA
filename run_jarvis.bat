@echo off
setlocal
cd /d "%~dp0"
title JARVIS AI OMEGA V7 - Terminal Agent
if not exist ".venv\Scripts\python.exe" (
  echo JARVIS environment not found. Run setup_windows.ps1 first.
  pause
  exit /b 1
)
if not exist ".env" echo No .env found. Local commands can still run; configure an AI key from setup for cloud chat.
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
