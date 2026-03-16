#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: sudo bash scripts/cvm_enable_postgres_remote.sh <ALLOW_IP> [DB_NAME] [DB_USER] [DB_PASSWORD]"
  echo "Example: sudo bash scripts/cvm_enable_postgres_remote.sh 116.238.250.233 xls_db xls_admin 'StrongPass123!'"
  exit 1
fi

ALLOW_IP="$1"
DB_NAME="${2:-xls_db}"
DB_USER="${3:-xls_admin}"
DB_PASSWORD="${4:-xls_admin_2024}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found. Install PostgreSQL first."
  exit 1
fi

CONFIG_FILE="$(sudo -u postgres psql -tAc "SHOW config_file;" | xargs)"
HBA_FILE="$(sudo -u postgres psql -tAc "SHOW hba_file;" | xargs)"

if [[ -z "$CONFIG_FILE" || -z "$HBA_FILE" ]]; then
  echo "Unable to locate PostgreSQL config files."
  exit 1
fi

cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$HBA_FILE" "${HBA_FILE}.bak.$(date +%Y%m%d%H%M%S)"

# Enable remote listen on all interfaces.
if grep -Eq "^[#\s]*listen_addresses\s*=" "$CONFIG_FILE"; then
  sed -E -i.bak "s|^[#\s]*listen_addresses\s*=.*|listen_addresses = '*'|" "$CONFIG_FILE"
else
  printf "\nlisten_addresses = '*'\n" >> "$CONFIG_FILE"
fi

# Add allowlist IP rule if absent.
RULE="host    all             all             ${ALLOW_IP}/32            md5"
if ! grep -Fq "$RULE" "$HBA_FILE"; then
  printf "\n%s\n" "$RULE" >> "$HBA_FILE"
fi

# Ensure app role and DB exist.
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO
\$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END
\$\$;
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
fi

# Restart service (supports common distro names).
if systemctl is-active --quiet postgresql; then
  systemctl restart postgresql
elif systemctl list-unit-files | grep -q '^postgresql-[0-9]'; then
  UNIT="$(systemctl list-unit-files | awk '/^postgresql-[0-9]+/ {print $1; exit}')"
  systemctl restart "$UNIT"
else
  service postgresql restart || true
fi

echo "Done. PostgreSQL remote access prepared."
echo "Allow IP: ${ALLOW_IP}/32"
echo "DB: ${DB_NAME}"
echo "User: ${DB_USER}"
