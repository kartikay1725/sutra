param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$InputFile = "backup.sql"
)

$ErrorActionPreference = 'Stop'

if (-not $DatabaseUrl) {
    Write-Error "DATABASE_URL environment variable is required."
    exit 1
}

if (-not (Test-Path $InputFile)) {
    Write-Error "Backup file $InputFile not found."
    exit 1
}

Write-Host "Restoring database from $InputFile..."

if (Get-Command psql -ErrorAction SilentlyContinue) {
    # Using --set ON_ERROR_STOP=on ensures psql exits on error
    psql --dbname="$DatabaseUrl" -f $InputFile -q -v ON_ERROR_STOP=1
} else {
    Write-Host "psql not found locally, attempting via Docker..."
    $CleanUrl = $DatabaseUrl -replace "postgresql\+psycopg://", "postgresql://"
    $DockerUrl = $CleanUrl -replace "localhost", "host.docker.internal" -replace "127.0.0.1", "host.docker.internal"
    
    Get-Content $InputFile | docker run -i --rm postgres:17 psql "$DockerUrl" -q -v ON_ERROR_STOP=1
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "psql restore failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
Write-Host "Restore successful."
