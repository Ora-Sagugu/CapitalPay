$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $projectRoot ".run"
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$clientDir = Join-Path $projectRoot "frontend\client_portal"
$customerDir = Join-Path $projectRoot "frontend\customer_portal"
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"

function Assert-Path {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw $Message
    }
}

function Test-Port {
    param([Parameter(Mandatory = $true)][int]$Port)

    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Start-ProjectService {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Command
    )

    $pidFile = Join-Path $runDir "$Name.pid"
    if (Test-Port -Port $Port) {
        Write-Host "[skip] $Name is already listening on port $Port." -ForegroundColor Yellow
        return
    }

    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    $cmdLine = "title CapitalPay - $Name && $Command"
    $process = Start-Process `
        -FilePath "cmd.exe" `
        -ArgumentList "/d", "/k", $cmdLine `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Minimized `
        -PassThru

    Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
    Write-Host "[start] $Name (port $Port, launcher PID $($process.Id))." -ForegroundColor Green
}

function Wait-Url {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "[ready] ${Name}: $Url" -ForegroundColor Green
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 750
        }
    } while ((Get-Date) -lt $deadline)

    throw "$Name did not become ready within $TimeoutSeconds seconds: $Url"
}

Assert-Path -Path $python -Message "Python virtual environment is missing. Run the first-time setup in START.md."
Assert-Path -Path (Join-Path $clientDir "node_modules") -Message "Client portal dependencies are missing. Run npm install in frontend\client_portal."
Assert-Path -Path (Join-Path $customerDir "node_modules") -Message "Customer portal dependencies are missing. Run npm install in frontend\customer_portal."
Assert-Path -Path $chrome -Message "Google Chrome was not found at: $chrome"

New-Item -ItemType Directory -Path $runDir -Force | Out-Null

$backendCommand = "`"$python`" manage.py runserver 1024"
Start-ProjectService -Name "backend" -Port 1024 -WorkingDirectory $projectRoot -Command $backendCommand
Start-ProjectService -Name "client-portal" -Port 1025 -WorkingDirectory $clientDir -Command "npm.cmd run dev"
Start-ProjectService -Name "agent-portal" -Port 1026 -WorkingDirectory $customerDir -Command "npm.cmd run dev:agent"
Start-ProjectService -Name "customer-portal" -Port 1027 -WorkingDirectory $customerDir -Command "npm.cmd run dev"

Wait-Url -Name "Django backend" -Url "http://127.0.0.1:1024/api/docs/"
Wait-Url -Name "Client portal" -Url "http://localhost:1025/"
Wait-Url -Name "Agent portal" -Url "http://localhost:1026/"
Wait-Url -Name "Customer portal" -Url "http://localhost:1027/"

Start-Process -FilePath $chrome -ArgumentList @(
    "--new-window",
    "http://localhost:1025/",
    "http://localhost:1026/login",
    "http://localhost:1027/login"
)

Write-Host ""
Write-Host "CapitalPay is running. Google Chrome has been opened." -ForegroundColor Cyan
