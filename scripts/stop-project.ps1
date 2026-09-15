$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $projectRoot ".run"
$services = @(
    @{ Name = "backend"; Port = 1024 },
    @{ Name = "client-portal"; Port = 1025 },
    @{ Name = "agent-portal"; Port = 1026 },
    @{ Name = "customer-portal"; Port = 1027 }
)

function Test-Port {
    param([Parameter(Mandatory = $true)][int]$Port)

    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

foreach ($service in $services) {
    $name = $service.Name
    $port = $service.Port
    $pidFile = Join-Path $runDir "$name.pid"

    if (-not (Test-Path -LiteralPath $pidFile)) {
        if (Test-Port -Port $port) {
            Write-Host "[skip] $name uses port $port but was not started by START_PROJECT.bat." -ForegroundColor Yellow
        }
        else {
            Write-Host "[skip] $name is not running."
        }
        continue
    }

    $launcherPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($launcherPid -match "^\d+$" -and (Get-Process -Id ([int]$launcherPid) -ErrorAction SilentlyContinue)) {
        & taskkill.exe /PID $launcherPid /T /F | Out-Null
        Write-Host "[stop] $name process tree stopped." -ForegroundColor Green
    }
    else {
        Write-Host "[clean] Removed stale PID file for $name." -ForegroundColor Yellow
    }

    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $runDir) {
    $remaining = Get-ChildItem -LiteralPath $runDir -Force -ErrorAction SilentlyContinue
    if (-not $remaining) {
        Remove-Item -LiteralPath $runDir -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Project services started by START_PROJECT.bat have been stopped." -ForegroundColor Cyan
