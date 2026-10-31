# Brightloop Subscription Management — Database Restore Script (PowerShell)
# Usage: .\scripts\restore.ps1 -BackupFile <path_to_dump> [-Force]

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found at: $BackupFile"
}

Write-Host "==========================================================" -ForegroundColor Red
Write-Host "  Brightloop Production Database Restore" -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red
Write-Host "TARGET BACKUP: $BackupFile" -ForegroundColor Yellow

if (-not $Force) {
    $Confirmation = Read-Host "WARNING: Restoring will overwrite existing tables in brightloop_subscriptions. Type 'RESTORE' to proceed"
    if ($Confirmation -ne "RESTORE") {
        Write-Host "Restore cancelled by operator." -ForegroundColor Cyan
        exit 0
    }
}

$DockerRunning = $false
try {
    $ContainerCheck = docker ps --filter "name=brightloop-db" --format "{{.Names}}" 2>$null
    if ($ContainerCheck -eq "brightloop-db") {
        $DockerRunning = $true
    }
} catch {}

if ($DockerRunning) {
    Write-Host "[Restore] Restoring into Docker container 'brightloop-db'..." -ForegroundColor Green
    Get-Content $BackupFile | docker exec -i brightloop-db psql -U postgres -d brightloop_subscriptions
} else {
    Write-Host "[Restore] Restoring via local psql..." -ForegroundColor Yellow
    $DbUrl = $env:SYNC_DATABASE_URL
    if (-not $DbUrl) {
        $DbUrl = "postgresql://postgres:postgres@localhost:5432/brightloop_subscriptions"
    }
    psql $DbUrl < $BackupFile
}

Write-Host "[Restore] Running Alembic migration check..." -ForegroundColor Green
cd "$PSScriptRoot\..\backend"
python -m alembic upgrade head

Write-Host "[Success] Database restore completed successfully." -ForegroundColor Green

