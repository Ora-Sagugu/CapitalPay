#!/usr/bin/env bash
# Idempotent server bootstrap for Ubuntu/Debian hosts.
# Run as a user with sudo:  bash deploy/install.sh
# Optional: SEED=1 bash deploy/install.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/capitalpay}"
WWW_DIR="${WWW_DIR:-/var/www/capitalpay}"
REPO_URL="${REPO_URL:-https://github.com/Ora-Sagugu/B2B-payment-system.git}"
BRANCH="${BRANCH:-main}"
SEED="${SEED:-0}"
# SKIP_BUILD=1: skip server-side frontend build (expects locally built dist uploaded with the code).
SKIP_BUILD="${SKIP_BUILD:-0}"
# Gunicorn worker count (2C2G low-memory box: 2; 2C4G+: 3).
WORKERS="${WORKERS:-3}"
# Set to 0 when MYSQL_HOST points to a managed MySQL / RDS instance.
PROVISION_MYSQL="${PROVISION_MYSQL:-1}"

echo "==> Installing OS packages"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip \
  nginx git curl ca-certificates rsync \
  build-essential libssl-dev
if [[ "${PROVISION_MYSQL}" == "1" ]]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server
fi

if [[ "${SKIP_BUILD}" != "1" ]] && ! command -v node >/dev/null 2>&1; then
  echo "==> Installing Node.js 20"
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi

echo "==> Fetching application code into ${APP_DIR}"
if [[ -f "${APP_DIR}/manage.py" ]]; then
  echo "==> Code already present in ${APP_DIR} (upload deploy), skipping git clone"
elif [[ ! -d "${APP_DIR}/.git" ]]; then
  sudo mkdir -p "$(dirname "${APP_DIR}")"
  sudo git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
  sudo git -C "${APP_DIR}" fetch --all
  sudo git -C "${APP_DIR}" checkout "${BRANCH}"
  sudo git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}" || true
fi
sudo chown -R "${USER}:${USER}" "${APP_DIR}"

cd "${APP_DIR}"

echo "==> Python venv + dependencies"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt -r requirements-prod.txt

if [[ ! -f .env ]]; then
  echo "==> Creating .env from deploy/env.production.example"
  cp deploy/env.production.example .env
  python - <<'PY'
from cryptography.fernet import Fernet
import secrets
from pathlib import Path
p = Path(".env")
text = p.read_text(encoding="utf-8")
text = text.replace("REPLACE_WITH_LONG_RANDOM_STRING", secrets.token_urlsafe(48))
text = text.replace("REPLACE_WITH_FERNET_KEY", Fernet.generate_key().decode())
text = text.replace("REPLACE_WITH_DATABASE_PASSWORD", secrets.token_urlsafe(32))
p.write_text(text, encoding="utf-8")
print("Generated DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY")
PY
fi

# Upgrade older deployments that predate MySQL settings without
# overwriting any explicitly configured managed-database values.
# Also map legacy POSTGRES_* keys to MYSQL_* when MYSQL_* are absent.
python - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
text = path.read_text(encoding="utf-8")
present = {
    line.split("=", 1)[0]
    for line in text.splitlines()
    if "=" in line and not line.lstrip().startswith("#")
}
env_map = {}
for line in text.splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, _, v = line.partition("=")
        env_map[k] = v

defaults = {
    "MYSQL_DATABASE": env_map.get("POSTGRES_DB", "b2b_payment"),
    "MYSQL_USER": env_map.get("POSTGRES_USER", "b2b_payment"),
    "MYSQL_PASSWORD": env_map.get("POSTGRES_PASSWORD", secrets.token_urlsafe(32)),
    "MYSQL_HOST": env_map.get("POSTGRES_HOST", "127.0.0.1"),
    "MYSQL_PORT": "3306",
    "MYSQL_SSL_MODE": "DISABLED",
    "MYSQL_CONN_MAX_AGE": env_map.get("POSTGRES_CONN_MAX_AGE", "60"),
}
# Prefer existing MYSQL_PORT if already present in file via defaults skip
if "MYSQL_PORT" in env_map and env_map["MYSQL_PORT"].strip():
    defaults["MYSQL_PORT"] = env_map["MYSQL_PORT"].strip()

missing = [f"{key}={value}" for key, value in defaults.items() if key not in present]
if missing:
    path.write_text(text.rstrip() + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
PY

set -a
# shellcheck disable=SC1091
source .env
set +a
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-b2b_payment.settings.production}"

for required_var in MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD MYSQL_HOST; do
  if [[ -z "${!required_var:-}" ]]; then
    echo "Missing ${required_var} in .env"
    exit 1
  fi
done

if [[ "${PROVISION_MYSQL}" == "1" ]]; then
  echo "==> Provisioning local MySQL 8"
  sudo systemctl enable --now mysql
  # mysql_native_password not required on MySQL 8.0 default caching_sha2_password;
  # PyMySQL supports caching_sha2_password.
  sudo mysql --protocol=socket <<SQL
CREATE DATABASE IF NOT EXISTS \`${MYSQL_DATABASE}\`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'localhost' IDENTIFIED BY '${MYSQL_PASSWORD}';
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASSWORD}';
ALTER USER '${MYSQL_USER}'@'localhost' IDENTIFIED BY '${MYSQL_PASSWORD}';
ALTER USER '${MYSQL_USER}'@'127.0.0.1' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'localhost';
GRANT ALL PRIVILEGES ON \`${MYSQL_DATABASE}\`.* TO '${MYSQL_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
echo "==> Import OFAC/UN sanctions lists (official full download; may take a few minutes)"
python manage.py import_all_sanctions --download --reset || echo "WARN: sanctions import failed; retry manually with import_all_sanctions"
if [[ "${SEED}" == "1" ]]; then
  python manage.py seed_data || true
fi

if [[ "${SKIP_BUILD}" == "1" ]]; then
  echo "==> SKIP_BUILD=1: skipping frontend build, publishing existing dist if present"
  sudo mkdir -p "${WWW_DIR}/client" "${WWW_DIR}/customer"
  if [[ -d frontend/client_portal/dist ]]; then
    sudo rsync -a --delete frontend/client_portal/dist/ "${WWW_DIR}/client/"
  fi
  if [[ -d frontend/customer_portal/dist ]]; then
    sudo rsync -a --delete frontend/customer_portal/dist/ "${WWW_DIR}/customer/"
  fi
else
  echo "==> Build frontends"
  (cd frontend/client_portal && npm ci && npm run build)
  (cd frontend/customer_portal && VITE_BASE=/customer/ npm ci && npm run build)

  echo "==> Publish static sites"
  sudo mkdir -p "${WWW_DIR}/client" "${WWW_DIR}/customer"
  sudo rsync -a --delete frontend/client_portal/dist/ "${WWW_DIR}/client/"
  sudo rsync -a --delete frontend/customer_portal/dist/ "${WWW_DIR}/customer/"
fi

echo "==> Permissions for www-data (media + static)"
sudo mkdir -p media staticfiles
sudo chown -R www-data:www-data "${APP_DIR}"
sudo chmod -R u+rwX,g+rwX "${APP_DIR}"

echo "==> Install systemd + nginx"
sudo cp deploy/systemd/capitalpay.service /etc/systemd/system/capitalpay.service
sudo sed -i "s/--workers [0-9]\+/--workers ${WORKERS}/" /etc/systemd/system/capitalpay.service
sudo systemctl daemon-reload
sudo systemctl enable capitalpay
sudo systemctl restart capitalpay

if [[ -d /etc/nginx/sites-available ]]; then
  sudo cp deploy/nginx/capitalpay.conf /etc/nginx/sites-available/capitalpay
  sudo ln -sf /etc/nginx/sites-available/capitalpay /etc/nginx/sites-enabled/capitalpay
  # Fresh ECS: drop Ubuntu default site so this app can bind port 80.
  sudo rm -f /etc/nginx/sites-enabled/default
else
  sudo cp deploy/nginx/capitalpay.conf /etc/nginx/conf.d/capitalpay.conf
fi
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

echo ""
echo "Deploy finished."
echo "  Ops portal:      http://<your public IP>/"
echo "  Customer portal: http://<your public IP>/customer/"
echo "  API docs:        http://<your public IP>/api/docs/"
echo "Check: sudo systemctl status capitalpay --no-pager"
