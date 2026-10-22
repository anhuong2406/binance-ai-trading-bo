[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# Run Unit and Integration Tests on Windows
# AI Binance Trading Company

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   CHẠY KIỂM THỬ HỆ THỐNG (TEST SUITE - 18 KỊCH BẢN)      " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "[LỖI] Chưa có môi trường .venv. Vui lòng chạy .\scripts\setup_windows.ps1 trước!" -ForegroundColor Red
    exit 1
}

Set-Location backend
& "..\.venv\Scripts\pytest.exe" tests -v
$exitCode = $LASTEXITCODE
Set-Location ..

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "[THÀNH CÔNG] Toàn bộ các bài kiểm thử đã PASS thành công 100%!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[CẢNH BÁO] Có bài test chưa đạt yêu cầu. Kiểm tra log ở trên." -ForegroundColor Red
}

exit $exitCode
