param([string]$PostgresBin = 'C:\Program Files\PostgreSQL\18\bin')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot
$clusterPath = Join-Path $projectRoot '.local\postgres'
$logPath = Join-Path $projectRoot '.local\postgres.log'
if (-not (Test-Path -LiteralPath (Join-Path $PostgresBin 'initdb.exe'))) { throw 'No se encontró PostgreSQL. Usa Docker o indica -PostgresBin.' }
New-Item -ItemType Directory -Path (Join-Path $projectRoot '.local') -Force | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
    Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination (Join-Path $projectRoot '.env')
}
if (-not (Test-Path -LiteralPath (Join-Path $clusterPath 'PG_VERSION'))) {
    $passwordFile = Join-Path $projectRoot '.local\bootstrap-password'
    [System.IO.File]::WriteAllText($passwordFile, 'polylepis_local')
    try {
        & (Join-Path $PostgresBin 'initdb.exe') -D $clusterPath -U polylepis -A scram-sha-256 --pwfile=$passwordFile --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar la instancia aislada.' }
    } finally { Remove-Item -LiteralPath $passwordFile -ErrorAction SilentlyContinue }
}
& (Join-Path $PostgresBin 'pg_ctl.exe') -D $clusterPath status | Out-Null
if ($LASTEXITCODE -ne 0) {
    $arguments = "-D `"$clusterPath`" -l `"$logPath`" -o `"-p 54329 -h 127.0.0.1`" -w start"
    $process = Start-Process -FilePath (Join-Path $PostgresBin 'pg_ctl.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "No se pudo iniciar PostgreSQL. Consulta $logPath" }
}
$env:PGPASSWORD = 'polylepis_local'
try {
    $exists = & (Join-Path $PostgresBin 'psql.exe') -h 127.0.0.1 -p 54329 -U polylepis -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='polylepis'"
    if ($exists -ne '1') {
        & (Join-Path $PostgresBin 'createdb.exe') -h 127.0.0.1 -p 54329 -U polylepis polylepis
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la base de datos polylepis.' }
    }
} finally { Remove-Item Env:PGPASSWORD }
Write-Output 'PostgreSQL del proyecto disponible en 127.0.0.1:54329. No se modificó el servicio existente.'
