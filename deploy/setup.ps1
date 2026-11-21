# CÀI ĐẶT TRÊN MÁY MỚI (chạy tự động lần đầu khi bấm start.bat; chạy lại bằng setup.bat)
#  1. Python 3.11–3.13   (thiếu thì cài bản 3.12 cho người dùng hiện tại, không cần quyền admin)
#  2. Node.js >= 18      (thiếu thì tải bản portable vào .tools\node)
#  3. PostgreSQL >= 15   (dùng bản đã cài trên máy, hoặc tải bản portable vào .tools\pgsql – không tạo service)
#  4. Tạo CSDL riêng của dự án trong .pgdata (cổng 5433) và nạp dữ liệu từ database\dti_platform.sql
#  5. Môi trường Python (backend\.venv) + thư viện; thư viện frontend + build giao diện
param([switch]$ResetData)   # -ResetData: xóa CSDL hiện tại và nạp lại từ file SQL
. "$PSScriptRoot\common.ps1"
New-Item -ItemType Directory -Force $Tools | Out-Null
Refresh-Path

# ------------------------------------------------------------------ 1. Python
Step "Kiểm tra Python (cần 3.11 – 3.13)"
function Find-Python {
    foreach ($v in @("3.13", "3.12", "3.11")) {
        if (Get-Command py.exe -ErrorAction SilentlyContinue) {
            $exe = & py.exe "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        }
    }
    foreach ($p in @("python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe")) {
        $c = Get-Command $p -ErrorAction SilentlyContinue
        if ($c -and $c.Source -notlike "*WindowsApps*") {
            $ver = & $c.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($ver -in @("3.11", "3.12", "3.13")) { return $c.Source }
        }
    }
    return $null
}
$py = Find-Python
if (-not $py) {
    Warn "Chưa có Python phù hợp – đang cài Python 3.12 (cho người dùng hiện tại)..."
    $inst = Join-Path $Tools "python-installer.exe"
    Download $PY_URL $inst
    Start-Process $inst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0" -Wait
    Remove-Item $inst -ErrorAction SilentlyContinue
    Refresh-Path
    $py = Find-Python
    if (-not $py) { Fail "Cài Python thất bại. Tải thủ công tại https://www.python.org/downloads/ (bản 3.12) rồi chạy lại." }
}
Ok "Python: $py"

# ------------------------------------------------------------------ 2. Node.js
Step "Kiểm tra Node.js (cần >= 18)"
$nodeOk = $false
if (Get-Command node.exe -ErrorAction SilentlyContinue) {
    $nv = (& node.exe --version) -replace '^v', ''
    if ([int]($nv.Split('.')[0]) -ge 18) { $nodeOk = $true }
}
if (-not $nodeOk) {
    Warn "Chưa có Node.js phù hợp – tải bản portable vào .tools\node ..."
    $zip = Join-Path $Tools "node.zip"
    Download $NODE_ZIP_URL $zip
    Expand-ZipFiltered $zip $Tools
    Remove-Item $zip
    if (Test-Path "$Tools\node") { Remove-Item -Recurse -Force "$Tools\node" }
    Get-ChildItem $Tools -Directory -Filter "node-v*" | Select-Object -First 1 | Rename-Item -NewName "node"
    Refresh-Path
}
Ok ("Node.js: " + (& node.exe --version))

# ------------------------------------------------------------------ 3. PostgreSQL
Step "Kiểm tra PostgreSQL (cần >= 15)"
$pg = Find-PgBin
if (-not $pg) {
    Warn "Chưa có PostgreSQL – tải bản portable (~300 MB) vào .tools\pgsql ..."
    $zip = Join-Path $Tools "pgsql.zip"
    Download $PG_ZIP_URL $zip
    if (Test-Path "$Tools\pgsql") { Remove-Item -Recurse -Force "$Tools\pgsql" }
    Expand-ZipFiltered $zip $Tools @("pgsql/pgAdmin 4/", "pgsql/StackBuilder/", "pgsql/doc/", "pgsql/symbols/")
    Remove-Item $zip
    Refresh-Path
    $pg = Find-PgBin
    if (-not $pg) { Fail "Không chuẩn bị được PostgreSQL" }
}
Ok "PostgreSQL: $pg ($(& "$pg\pg_ctl.exe" --version))"

# ------------------------------------------------------------------ 4. CSDL riêng của dự án
Step "Chuẩn bị CSDL (thư mục .pgdata, cổng $PgPort)"
if ($ResetData -and (Test-Path $PgData)) {
    if (Pg-Running $pg) { & "$pg\pg_ctl.exe" -D $PgData stop -m fast *> $null }
    Remove-Item -Recurse -Force $PgData
    Warn "Đã xóa CSDL cũ"
}
if (-not (Test-Path "$PgData\PG_VERSION")) {
    $pw = Join-Path $Tools "pw.txt"
    Set-Content -Path $pw -Value $PgPass -Encoding ASCII -NoNewline
    & "$pg\initdb.exe" -D $PgData -U $PgUser --pwfile=$pw -E UTF8 --locale=C -A scram-sha-256 *> "$Tools\initdb.log"
    Remove-Item $pw
    if (-not (Test-Path "$PgData\PG_VERSION")) { Fail "initdb thất bại – xem .tools\initdb.log" }
    Ok "Đã khởi tạo cluster PostgreSQL"
}
if ((Port-InUse $PgPort) -and -not (Pg-Running $pg)) { Fail "Cổng $PgPort đang bị chương trình khác dùng" }
Start-Pg $pg
$exists = Psql $pg "postgres" @("-tAc", "SELECT 1 FROM pg_database WHERE datname='$PgDb'")
if ("$exists".Trim() -ne "1") {
    Psql $pg "postgres" @("-c", "CREATE DATABASE $PgDb ENCODING 'UTF8' TEMPLATE template0") | Out-Null
    Ok "Đã tạo CSDL $PgDb"
}
$tables = Psql $pg $PgDb @("-tAc", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if ([int]("$tables".Trim()) -eq 0) {
    if (Test-Path $DumpSql) {
        Write-Host "    Nạp dữ liệu từ database\dti_platform.sql (khoảng 1 phút)..."
        $sql = $DumpSql
        $major = [int]((& "$pg\pg_ctl.exe" --version) -replace '^\D*(\d+).*$', '$1')
        if ($major -lt 17) {   # bản dump từ PG 17 có lệnh SET transaction_timeout mà bản cũ không hiểu
            $sql = Join-Path $Tools "dump_compat.sql"
            Get-Content $DumpSql -Encoding UTF8 | Where-Object { $_ -notmatch '^SET transaction_timeout' } | Set-Content $sql -Encoding UTF8
        }
        Psql $pg $PgDb @("-f", $sql) 2>&1 | Where-Object { "$_" -match "ERROR" } | ForEach-Object { Warn "$_" }
        $n = Psql $pg $PgDb @("-tAc", "SELECT count(*) FROM users")
        Ok "Đã nạp dữ liệu – $("$n".Trim()) tài khoản"
        if (Test-Path "$DbDir\uploads") {
            New-Item -ItemType Directory -Force "$Backend\uploads" | Out-Null
            Copy-Item "$DbDir\uploads\*" "$Backend\uploads" -Recurse -Force -ErrorAction SilentlyContinue
        }
    } else {
        $seedNeeded = $true
        Warn "Không có database\dti_platform.sql – sẽ sinh dữ liệu mẫu bằng seed.py sau khi cài thư viện"
    }
} else { Ok "CSDL đã có dữ liệu – giữ nguyên (dùng setup.bat -ResetData để nạp lại)" }

# ------------------------------------------------------------------ 5. Backend
Step "Môi trường Python cho backend (backend\.venv)"
if (-not (Test-Path $VenvPy)) {
    & $py -m venv "$Backend\.venv"
    if (-not (Test-Path $VenvPy)) { Fail "Không tạo được môi trường ảo Python" }
}
& $VenvPy -m pip install --disable-pip-version-check -q --upgrade pip
& $VenvPy -m pip install --disable-pip-version-check -q -r "$Backend\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "Cài thư viện Python thất bại (kiểm tra kết nối mạng)" }
Ok "Đã cài thư viện Python"
$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
    $secret = -join ((48..57) + (97..122) | Get-Random -Count 40 | ForEach-Object { [char]$_ })
    @("DATABASE_URL=postgresql+psycopg://${PgUser}:${PgPass}@localhost:$PgPort/$PgDb", "JWT_SECRET=$secret",
      "CORS_ORIGINS=http://localhost:$AppPort,http://127.0.0.1:$AppPort,http://localhost:5173") | Set-Content $envFile -Encoding ASCII
    Ok "Đã tạo backend\.env"
}
if ($seedNeeded) {
    Push-Location $Backend; $env:PYTHONIOENCODING = "utf-8"; & $VenvPy -m scripts.seed; Pop-Location
}

# ------------------------------------------------------------------ 6. Frontend
Step "Thư viện & build giao diện (frontend)"
Push-Location $Frontend
& npm.cmd ci --no-audit --no-fund --loglevel=error
if ($LASTEXITCODE -ne 0) { & npm.cmd install --no-audit --no-fund --loglevel=error }
& npm.cmd run build *> "$Tools\build.log"
$built = Test-Path "$Frontend\dist\index.html"
Pop-Location
if (-not $built) { Fail "Build giao diện thất bại – xem .tools\build.log" }
Ok "Đã build giao diện (frontend\dist)"

Set-Content (Join-Path $Tools "setup.done") (Get-Date -Format s)
Write-Host ""
Write-Host "CÀI ĐẶT HOÀN TẤT." -ForegroundColor Green
