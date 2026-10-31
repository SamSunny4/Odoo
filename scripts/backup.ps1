# Brightloop Subscription Management — Database Backup Script (PowerShell)
# Usage: .\scripts\backup.ps1 [-OutputFile <path>]

param(
    [string]$OutputFile = ""
)

$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $PSScriptRoot "..\backups"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

if (-not $OutputFile) {
    $OutputFile = Join-Path $BackupDir "brightloop_backup_$Timestamp.sql"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Brightloop Production Database Backup — $Timestamp" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check if Docker container brightloop-db is running
$DockerRunning = $false
try {
    $ContainerCheck = docker ps --filter "name=brightloop-db" --format "{{.Names}}" 2>$null
    if ($ContainerCheck -eq "brightloop-db") {
        $DockerRunning = $true
    }
} catch {}

if ($DockerRunning) {
    Write-Host "[Backup] Dumping from running Docker container 'brightloop-db'..." -ForegroundColor Green
    docker exec -t brightloop-db pg_dump -U postgres -d brightloop_subscriptions --clean --if-exists > $OutputFile
} else {
    Write-Host "[Backup] Dumping via local pg_dump..." -ForegroundColor Yellow
    $DbUrl = $env:SYNC_DATABASE_URL
    if (-not $DbUrl) {
        $DbUrl = "postgresql://postgres:postgres@localhost:5432/brightloop_subscriptions"
    }
    pg_dump $DbUrl --clean --if-exists > $OutputFile
}

if (Test-Path $OutputFile) {
    $Size = (Get-Item $OutputFile).Length
    $Hash = (Get-FileHash -Path $OutputFile -Algorithm SHA256).Hash
    Write-Host "[Success] Backup created successfully!" -ForegroundColor Green
    Write-Host "  Path:   $OutputFile"
    Write-Host "  Size:   $Size bytes"
    Write-Host "  SHA256: $Hash"
} else {
    Write-Error "[Error] Backup file was not generated."
}

