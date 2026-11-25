$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
$marker = Join-Path $projectRoot '.local\api.json'
if (Test-Path -LiteralPath $marker) {
    $entry = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    $process = Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime() -eq ([datetime]$entry.started).ToUniversalTime()) {
        taskkill /PID $entry.pid /T /F | Out-Null
        $process.WaitForExit()
    }
    Remove-Item -LiteralPath $marker
}
& (Join-Path $PSScriptRoot 'start-local.ps1')
