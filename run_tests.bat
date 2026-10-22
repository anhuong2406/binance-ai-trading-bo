@echo off
title AI Binance Trading Company - Tests
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_tests.ps1"
pause
