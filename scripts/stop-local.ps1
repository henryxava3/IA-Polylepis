param([switch]$Docker)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
if ($Docker) { Push-Location $projectRoot; try { docker compose stop } finally { Pop-Location }; exit }
foreach ($serviceName in @('api','web')) {
    $marker = Join-Path $projectRoot ('.local\' + $serviceName + '.json')
    if (Test-Path -LiteralPath $marker) {
        $entry = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
        $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime() -eq ([datetime]$entry.started).ToUniversalTime()) {
            # /T stops only this recorded process tree; never a global node/python process list.
            taskkill /PID $entry.pid /T /F | Out-Null
        }
        Remove-Item -LiteralPath $marker
    }
}
$clusterPath = Join-Path $projectRoot '.local\postgres'
if (Test-Path -LiteralPath (Join-Path $clusterPath 'PG_VERSION')) {
    & 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D $clusterPath -m fast -w stop
}
Write-Output 'Procesos del proyecto detenidos; datos conservados.'
