[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Startup Script for Windows PowerShell
# AI Binance Trading Company

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   KHỞI CHẠY AI BINANCE TRADING COMPANY                   " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "[LỖI] Chưa có môi trường .venv. Vui lòng chạy .\scripts\setup_windows.ps1 trước!" -ForegroundColor Red
    exit 1
}

# Khởi động Backend + Static Frontend trên port 8000
Write-Host "[INFO] Đang khởi động máy chủ tại http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "[INFO] Nhấn Ctrl+C để dừng hệ thống." -ForegroundColor Gray
Write-Host ""

# Mở trình duyệt sau 2 giây
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

Set-Location backend
& "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
