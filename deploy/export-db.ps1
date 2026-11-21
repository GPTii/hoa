# Xuất toàn bộ CSDL hiện tại ra database\dti_platform.sql (+ tệp đính kèm) để đưa lên git.
# Chạy trước mỗi lần push nếu muốn máy khác có dữ liệu y hệt máy này:  export-db.bat
. "$PSScriptRoot\common.ps1"

$bin = Find-PgBin
if (-not $bin) { Fail "Không tìm thấy PostgreSQL – chạy start.bat trước" }
if (-not (Test-Path "$PgData\PG_VERSION")) { Fail "Chưa có CSDL (.pgdata) để xuất" }
Start-Pg $bin
New-Item -ItemType Directory -Force $DbDir | Out-Null

Step "Xuất CSDL $PgDb -> database\dti_platform.sql"
$env:PGPASSWORD = $PgPass
$tmp = "$DumpSql.tmp"
& "$bin\pg_dump.exe" -h localhost -p $PgPort -U $PgUser -d $PgDb --no-owner --no-privileges --encoding=UTF8 -f $tmp
if ($LASTEXITCODE -ne 0) { Remove-Item $tmp -ErrorAction SilentlyContinue; Fail "pg_dump thất bại" }
Move-Item -Force $tmp $DumpSql
Ok ("Đã xuất {0:N1} MB" -f ((Get-Item $DumpSql).Length / 1MB))

Step "Sao chép tệp đính kèm -> database\uploads"
$up = Join-Path $Backend "uploads"
$dst = Join-Path $DbDir "uploads"
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
New-Item -ItemType Directory -Force $dst | Out-Null
if (Test-Path $up) { Copy-Item "$up\*" $dst -Recurse -Force -ErrorAction SilentlyContinue }
Ok ("{0} tệp" -f (Get-ChildItem $dst -File -Recurse).Count)
Write-Host ""
Write-Host "Xong. Commit thư mục database\ rồi push – máy mới chạy start.bat sẽ có dữ liệu giống hệt." -ForegroundColor Green
