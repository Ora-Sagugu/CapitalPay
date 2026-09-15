#!/usr/bin/env bash
# Canonical remote bootstrap for an Aliyun ECS deployment.
# Usage: PUBLIC_IP=203.0.113.10 bash deploy/remote_install_aliyun.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/capitalpay}"
ARCHIVE="${ARCHIVE:-/tmp/capitalpay.tar.gz}"
PUBLIC_IP="${PUBLIC_IP:-}"
SEED="${SEED:-1}"
WORKERS="${WORKERS:-2}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/remote_install_aliyun.sh"
  exit 1
fi

if [[ -z "${PUBLIC_IP}" ]]; then
  echo "PUBLIC_IP is required, for example: PUBLIC_IP=203.0.113.10 bash deploy/remote_install_aliyun.sh"
  exit 1
fi

if [[ ! -f "${ARCHIVE}" ]]; then
  echo "Deployment archive not found: ${ARCHIVE}"
  exit 1
fi

if ! swapon --show | grep -q '/swapfile'; then
  echo "==> Adding 2G swap"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Extracting application"
mkdir -p "${APP_DIR}"
tar -xzf "${ARCHIVE}" -C "${APP_DIR}"
cd "${APP_DIR}"

APP_DIR="${APP_DIR}" SEED="${SEED}" SKIP_BUILD=1 WORKERS="${WORKERS}" bash deploy/install.sh

echo "==> Applying public URL settings"
PUBLIC_IP="${PUBLIC_IP}" .venv/bin/python - <<'PY'
import os
from pathlib import Path

public_ip = os.environ["PUBLIC_IP"]
path = Path(".env")
updates = {
    "ALLOWED_HOSTS": public_ip,
    "CSRF_TRUSTED_ORIGINS": f"http://{public_ip},https://{public_ip}",
    "CORS_ALLOWED_ORIGINS": f"http://{public_ip},https://{public_ip}",
    "CASHIER_BASE_URL": f"http://{public_ip}/customer/pay",
}
seen = set()
lines = []
for line in path.read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        line = f"{key}={updates[key]}"
        seen.add(key)
    lines.append(line)
for key, value in updates.items():
    if key not in seen:
        lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "==> Finalizing runtime permissions"
chown -R www-data:www-data "${APP_DIR}"
chmod 640 "${APP_DIR}/.env"
systemctl restart capitalpay

healthy=0
for _ in $(seq 1 20); do
  if curl -fsSI --max-time 5 -H "Host: ${PUBLIC_IP}" http://127.0.0.1:1024/api/docs/ >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "${healthy}" != "1" ]]; then
  systemctl status capitalpay --no-pager || true
  echo "Backend health check failed"
  exit 1
fi
rm -f "${ARCHIVE}"

echo ""
echo "Remote install finished."
echo "  Ops portal:      http://${PUBLIC_IP}/"
echo "  Customer portal: http://${PUBLIC_IP}/customer/"
echo "  API docs:        http://${PUBLIC_IP}/api/docs/"
systemctl status capitalpay --no-pager || true
