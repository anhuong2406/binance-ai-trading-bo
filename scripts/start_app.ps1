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

# Tự động giải phóng cổng 8000 nếu có tiến trình cũ đang chạy chiếm giữ
$portOccupied = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($portOccupied) {
    foreach ($pidToKill in $portOccupied) {
        if ($pidToKill -gt 0) {
            Write-Host "[INFO] Đang dọn dẹp tiến trình cũ chiếm cổng 8000 (PID: $pidToKill)..." -ForegroundColor Yellow
            Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 800
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
& "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
