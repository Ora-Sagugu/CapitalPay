# Upload and install CapitalPay on Aliyun ECS (password SSH).
# Usage: $env:ECS_HOST = "203.0.113.10"; .\scripts\deploy-to-aliyun.ps1

param(
  [string]$HostName = $env:ECS_HOST,
  [string]$User = "root"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($HostName)) {
  throw "Set ECS_HOST or pass -HostName before deploying."
}
if ($HostName -notmatch '^[A-Za-z0-9.-]+$') {
  throw "HostName may contain only letters, digits, dots, and hyphens."
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> Building frontends"
Push-Location frontend\client_portal
npm ci
npm run build
Pop-Location
Push-Location frontend\customer_portal
npm ci
$env:VITE_BASE = "/customer/"
npm run build
Pop-Location

Write-Host "==> Packaging"
$archive = Join-Path $root "capitalpay.tar.gz"
if (Test-Path $archive) { Remove-Item $archive -Force }
tar -czf $archive `
  --exclude="node_modules" --exclude=".venv" --exclude="__pycache__" `
  --exclude="db.sqlite3" --exclude=".git" `
  apps b2b_payment frontend deploy manage.py requirements.txt requirements-prod.txt

try {
  Write-Host "==> Uploading to ${User}@${HostName}:/tmp/"
  scp -o StrictHostKeyChecking=accept-new $archive "${User}@${HostName}:/tmp/"

  Write-Host "==> Running remote install (enter root password again if prompted)"
  ssh -o StrictHostKeyChecking=accept-new "${User}@${HostName}" @"
set -e
tar -xOf /tmp/capitalpay.tar.gz deploy/remote_install_aliyun.sh > /tmp/capitalpay-remote-install.sh
PUBLIC_IP='${HostName}' bash /tmp/capitalpay-remote-install.sh
rm -f /tmp/capitalpay-remote-install.sh
"@
}
finally {
  Remove-Item $archive -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Deploy finished. Open:"
Write-Host "  http://${HostName}/"
Write-Host "  http://${HostName}/customer/"
Write-Host "  http://${HostName}/api/docs/"
