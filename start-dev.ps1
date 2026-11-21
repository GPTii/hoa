# Khởi động toàn bộ hệ thống ở chế độ phát triển (Windows PowerShell)
#   .\start-dev.ps1            -> chạy DB + backend + frontend
#   .\start-dev.ps1 -Seed      -> tạo lại CSDL + dữ liệu mô phỏng trước khi chạy
param([switch]$Seed)

$root = $PSScriptRoot
$pg = "C:\Program Files\PostgreSQL\17\bin"

# 1) PostgreSQL riêng của dự án (cổng 5433, dữ liệu trong .pgdata)
& "$pg\pg_ctl.exe" -D "$root\.pgdata" status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Khởi động PostgreSQL (cổng 5433)..."
    & "$pg\pg_ctl.exe" -D "$root\.pgdata" -o "-p 5433" -l "$root\.pgdata\server.log" start
}

# 2) Dữ liệu mô phỏng
if ($Seed) {
    Push-Location "$root\backend"; & .\.venv\Scripts\python.exe -m scripts.seed; Pop-Location
}

# 3) Backend FastAPI (http://localhost:8000, tài liệu API: /docs)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload"

# 4) Frontend React (http://localhost:5173)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host "Mở http://localhost:5173  (tài khoản: admin / 123456)"
