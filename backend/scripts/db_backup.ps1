param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$OutputFile = "backup.sql"
)

$ErrorActionPreference = 'Stop'

if (-not $DatabaseUrl) {
    Write-Error "DATABASE_URL environment variable is required."
    exit 1
}

if ($DatabaseUrl.StartsWith("sqlite")) {
    Write-Error "Backup script only supports PostgreSQL."
    exit 1
}

# Protect passwords by not printing DatabaseUrl directly
Write-Host "Backing up database to $OutputFile..."

if (Get-Command pg_dump -ErrorAction SilentlyContinue) {
    pg_dump --dbname="$DatabaseUrl" -F p -f $OutputFile --clean --if-exists
} else {
    Write-Host "pg_dump not found locally, attempting via Docker..."
    # Convert postgresql+psycopg to postgresql
    $CleanUrl = $DatabaseUrl -replace "postgresql\+psycopg://", "postgresql://"
    
    # We use a temporary container so we can use the full URL 
    # to connect to the host machine's port. We must use host.docker.internal
    $DockerUrl = $CleanUrl -replace "localhost", "host.docker.internal" -replace "127.0.0.1", "host.docker.internal"
    
    docker run --rm postgres:17 pg_dump "$DockerUrl" -F p --clean --if-exists > $OutputFile
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_dump failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
Write-Host "Backup successful."
