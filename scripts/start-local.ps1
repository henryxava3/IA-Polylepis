param([switch]$Docker)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if ($Docker) {
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw 'Docker no pudo iniciar la aplicación.' }
    Write-Output 'Aplicación: http://localhost:3000 · API: http://localhost:8000/docs'
    exit
}
& (Join-Path $PSScriptRoot 'setup-native.ps1')
$backendPath = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.cache\uv'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot '.runtime\python'
    Push-Location -LiteralPath $backendPath
    try { uv sync --frozen --python 3.12; if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación Python.' } } finally { Pop-Location }
}
$frontendPath = Join-Path $projectRoot 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $frontendPath 'node_modules'))) {
    Push-Location -LiteralPath $frontendPath
    try { npm ci --cache ../.cache/npm; if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación web.' } } finally { Pop-Location }
}
$env:NEXT_TELEMETRY_DISABLED = '1'
$services = @(
    @{name='api'; path=$pythonPath; args='-m uvicorn app.main:app --host 127.0.0.1 --port 8000'; cwd=$backendPath; port=8000},
    @{name='web'; path=(Get-Command node).Source; args='node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3000'; cwd=$frontendPath; port=3000}
)
foreach ($service in $services) {
    $marker = Join-Path $projectRoot ('.local\' + $service.name + '.json')
    if (Test-Path -LiteralPath $marker) {
        $old = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $old.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime() -eq ([datetime]$old.started).ToUniversalTime()) { continue }
    }
    $portInUse = Get-NetTCPConnection -LocalPort $service.port -State Listen -ErrorAction SilentlyContinue
    if ($portInUse) { throw "El puerto $($service.port) está ocupado por otro proceso. No se detendrá automáticamente." }
    $process = Start-Process -FilePath $service.path -ArgumentList $service.args -WorkingDirectory $service.cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot ('.local\' + $service.name + '.out.log')) -RedirectStandardError (Join-Path $projectRoot ('.local\' + $service.name + '.err.log'))
    @{pid=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $marker
}
Write-Output 'Aplicación: http://localhost:3000 · API: http://localhost:8000/docs'
Write-Output 'Los procesos arrancan en segundo plano. Para detenerlos: .\scripts\stop-local.ps1'
