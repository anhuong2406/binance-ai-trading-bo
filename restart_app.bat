@echo off
title AI Binance Trading Company - Restarting
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_app.ps1"
pause
