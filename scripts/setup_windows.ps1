[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Setup Script for Windows PowerShell
# AI Binance Trading Company

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   AI BINANCE TRADING COMPANY - CÀI ĐẶT TRÊN WINDOWS      " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Kiểm tra Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[LỖI] Không tìm thấy Python trên hệ thống. Vui lòng cài đặt Python 3.12+!" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Đã tìm thấy Python: $($pythonCmd.Source)" -ForegroundColor Green

# 2. Khởi tạo môi trường ảo Python .venv
if (-not (Test-Path ".venv")) {
    Write-Host "[INFO] Đang tạo môi trường ảo Python .venv..." -ForegroundColor Cyan
    python -m venv .venv
}
Write-Host "[OK] Môi trường ảo .venv đã sẵn sàng." -ForegroundColor Green

# 3. Cài đặt Python dependencies
Write-Host "[INFO] Đang cài đặt thư viện backend..." -ForegroundColor Cyan
.\.venv\Scripts\pip.exe install -r backend/requirements.txt --quiet
Write-Host "[OK] Thư viện backend đã cài đặt thành công." -ForegroundColor Green

# 4. Kiểm tra Node / NPM
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host "[CẢNH BÁO] Không tìm thấy npm. Nếu bạn chỉ muốn chạy bản dựng sẵn thì không cần npm." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Đang cài đặt thư viện frontend (npm install)..." -ForegroundColor Cyan
    Set-Location frontend
    npm install --quiet
    Write-Host "[INFO] Đang build giao diện frontend (npm run build)..." -ForegroundColor Cyan
    npm run build
    Set-Location ..
    Write-Host "[OK] Frontend đã được biên dịch thành công vào frontend/dist." -ForegroundColor Green
}

# 5. Khởi tạo file .env nếu chưa có
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Đã tạo file .env mẫu từ .env.example." -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   CÀI ĐẶT HOÀN TẤT! ĐỂ KHỞI CHẠY ỨNG DỤNG:               " -ForegroundColor Yellow
Write-Host "   Chạy lệnh: .\scripts\start_app.ps1                      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
