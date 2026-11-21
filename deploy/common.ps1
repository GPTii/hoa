# Hàm dùng chung cho setup.ps1 / run.ps1 / export-db.ps1
$ErrorActionPreference = "Continue"   # PS 5.1: "Stop" + chuyển hướng stderr của lệnh ngoài sẽ ném lỗi giả
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest nhanh hơn nhiều khi tắt thanh tiến trình

$Root    = Split-Path -Parent $PSScriptRoot
$Tools   = Join-Path $Root ".tools"
$PgData  = Join-Path $Root ".pgdata"
$DbDir   = Join-Path $Root "database"
$DumpSql = Join-Path $DbDir "dti_platform.sql"
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy  = Join-Path $Backend ".venv\Scripts\python.exe"

$PgPort = 5433
$PgUser = "dti"
$PgPass = "dtipass"
$PgDb   = "dti_platform"
$AppPort = 8000

$PG_ZIP_URL   = "https://get.enterprisedb.com/postgresql/postgresql-17.6-1-windows-x64-binaries.zip"
$NODE_ZIP_URL = "https://nodejs.org/dist/v20.18.1/node-v20.18.1-win-x64.zip"
$PY_URL       = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host ""; Write-Host "LỖI: $msg" -ForegroundColor Red; exit 1 }

# Giải nén zip nhưng bỏ qua các thư mục không cần (VD pgAdmin trong gói PostgreSQL có đường dẫn quá dài > 260 ký tự)
function Expand-ZipFiltered($zip, $dest, [string[]]$skip = @()) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $z = [IO.Compression.ZipFile]::OpenRead($zip)
    try {
        foreach ($e in $z.Entries) {
            $name = $e.FullName -replace '\\', '/'
            if ($skip | Where-Object { $name.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }) { continue }
            $target = Join-Path $dest $name
            if ($name.EndsWith("/")) { New-Item -ItemType Directory -Force $target | Out-Null; continue }
            New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $target, $true)
        }
    } finally { $z.Dispose() }
}

function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $u = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$m;$u"
    foreach ($p in @("$Tools\node", "$Tools\pgsql\bin")) { if (Test-Path $p) { $env:Path = "$p;$env:Path" } }
}

function Download($url, $out) {
    Write-Host "    Tải $url"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
}

# ---------- PostgreSQL: dùng bản đã cài trên máy (>= 15) hoặc bản portable trong .tools\pgsql
function Find-PgBin {
    $cands = @()
    if (Test-Path "$Tools\pgsql\bin\pg_ctl.exe") { $cands += "$Tools\pgsql\bin" }
    $cmd = Get-Command pg_ctl.exe -ErrorAction SilentlyContinue
    if ($cmd) { $cands += (Split-Path $cmd.Source) }
    foreach ($base in @("$env:ProgramFiles\PostgreSQL", "${env:ProgramFiles(x86)}\PostgreSQL")) {
        if (Test-Path $base) {
            Get-ChildItem $base -Directory | Sort-Object { [int]($_.Name -replace '\D.*$', '0') } -Descending |
                ForEach-Object { if (Test-Path "$($_.FullName)\bin\pg_ctl.exe") { $cands += "$($_.FullName)\bin" } }
        }
    }
    foreach ($c in $cands) {
        $v = & "$c\pg_ctl.exe" --version 2>$null
        if ($v -match '(\d+)\.') { if ([int]$Matches[1] -ge 15) { return $c } }
    }
    return $null
}

function Pg-Running($bin) {
    & "$bin\pg_ctl.exe" -D $PgData status *> $null
    return ($LASTEXITCODE -eq 0)
}

function Start-Pg($bin) {
    if (Pg-Running $bin) { return }
    $log = Join-Path $PgData "server.log"
    # Chạy pg_ctl trong tiến trình riêng, không nối ống output: nếu chuyển hướng (*> $null) thì tiến trình postgres
    # con giữ ống mở và PowerShell chờ mãi không trả về.
    $p = Start-Process -FilePath "$bin\pg_ctl.exe" -ArgumentList @("-D", "`"$PgData`"", "-o", "`"-p $PgPort`"", "-l", "`"$log`"", "-w", "-t", "60", "start") `
        -WindowStyle Hidden -PassThru
    $p.WaitForExit(90000) | Out-Null
    if (-not (Pg-Running $bin)) { Fail "Không khởi động được PostgreSQL – xem $log" }
}

function Psql($bin, $db, [string[]]$extra) {
    $env:PGPASSWORD = $PgPass
    & "$bin\psql.exe" -h localhost -p $PgPort -U $PgUser -d $db -v ON_ERROR_STOP=0 -q @extra
}

function Port-InUse($port) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $port); $c.Close(); return $true } catch { return $false }
}
