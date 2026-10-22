@echo off
title AI Binance Trading Company - Setup
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup_windows.ps1"
pause
