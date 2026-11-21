# CHẠY ỨNG DỤNG: lần đầu tự cài đặt, sau đó bật CSDL + máy chủ và mở http://localhost:8000
#   Đóng cửa sổ này (hoặc Ctrl+C) để tắt ứng dụng.
. "$PSScriptRoot\common.ps1"
$Host.UI.RawUI.WindowTitle = "DTI Platform"

$ready = (Test-Path (Join-Path $Tools "setup.done")) -and (Test-Path $VenvPy) -and (Test-Path "$Frontend\dist\index.html") -and (Test-Path "$PgData\PG_VERSION")
if (-not $ready) {
    Write-Host "Lần chạy đầu tiên trên máy này – tiến hành cài đặt (5–15 phút tùy tốc độ mạng)..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup.ps1"
    if (-not (Test-Path (Join-Path $Tools "setup.done"))) { exit 1 }
}
Refresh-Path

Step "Khởi động PostgreSQL (cổng $PgPort)"
$pg = Find-PgBin
if (-not $pg) { Fail "Không tìm thấy PostgreSQL – chạy setup.bat" }
Start-Pg $pg
Ok "PostgreSQL đang chạy"

Step "Khởi động máy chủ ứng dụng (cổng $AppPort)"
if (Port-InUse $AppPort) {
    Warn "Cổng $AppPort đang có chương trình khác (có thể ứng dụng đã chạy ở cửa sổ khác)."
    Warn "Mở thử http://localhost:$AppPort – nếu không vào được, đóng chương trình đang dùng cổng $AppPort rồi chạy lại."
    Start-Process "http://localhost:$AppPort"
    exit 0
}
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $Root ".api.log"
$proc = Start-Process -FilePath $VenvPy -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $AppPort" `
    -WorkingDirectory $Backend -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
$up = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) { break }
    try { Invoke-WebRequest "http://127.0.0.1:$AppPort/api/auth/public-config" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true; break } catch {}
}
if (-not $up) {
    Get-Content "$log.err" -Tail 20 -ErrorAction SilentlyContinue
    Fail "Máy chủ không khởi động được (log: .api.log.err)"
}

$url = "http://localhost:$AppPort"
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "    DTI Platform đang chạy:  $url" -ForegroundColor Green
Write-Host "    Tài khoản quản trị: admin / 123456  (các tài khoản thử nghiệm hiện ở trang đăng nhập)" -ForegroundColor Green
Write-Host "    Tài liệu API: $url/docs" -ForegroundColor Green
Write-Host "    Đóng cửa sổ này hoặc bấm Ctrl+C để tắt." -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Start-Process $url

try { Wait-Process -Id $proc.Id }
finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    & "$pg\pg_ctl.exe" -D $PgData stop -m fast *> $null
    Write-Host "Đã tắt ứng dụng."
}
