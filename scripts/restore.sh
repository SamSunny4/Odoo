#!/usr/bin/env bash
# Brightloop Subscription Management — Database Restore Script (POSIX)
# Usage: ./scripts/restore.sh <path_to_sql_dump> [--force]

set -euo pipefail

BACKUP_FILE="${1:-}"
FORCE="${2:-}"

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "Usage: $0 <path_to_sql_dump> [--force]" >&2
    exit 1
fi

echo "=========================================================="
echo "  Brightloop Production Database Restore"
echo "=========================================================="
echo "TARGET: $BACKUP_FILE"

if [ "$FORCE" != "--force" ]; then
    read -r -p "WARNING: Restoring will overwrite existing tables. Type 'RESTORE' to proceed: " CONFIRM
    if [ "$CONFIRM" != "RESTORE" ]; then
        echo "Restore cancelled by user."
        exit 0
    fi
fi

if docker ps --format '{{.Names}}' | grep -q "^brightloop-db$"; then
    echo "[Restore] Restoring into Docker container 'brightloop-db'..."
    docker exec -i brightloop-db psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-brightloop_subscriptions}" < "$BACKUP_FILE"
else
    echo "[Restore] Restoring via local psql..."
    DB_URL="${SYNC_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/brightloop_subscriptions}"
    psql "$DB_URL" < "$BACKUP_FILE"
fi

echo "[Restore] Checking migrations..."
cd "$(dirname "$0")/../backend"
python -m alembic upgrade head

echo "[Success] Database restore completed successfully."

