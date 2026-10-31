#!/usr/bin/env bash
# Brightloop Subscription Management — Database Backup Script (POSIX)
# Usage: ./scripts/backup.sh [output_file]

set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$(dirname "$0")/../backups"
mkdir -p "$BACKUP_DIR"

OUTPUT_FILE="${1:-$BACKUP_DIR/brightloop_backup_${TIMESTAMP}.sql}"

echo "=========================================================="
echo "  Brightloop Production Database Backup — $TIMESTAMP"
echo "=========================================================="

if docker ps --format '{{.Names}}' | grep -q "^brightloop-db$"; then
    echo "[Backup] Dumping from running Docker container 'brightloop-db'..."
    docker exec -t brightloop-db pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-brightloop_subscriptions}" --clean --if-exists > "$OUTPUT_FILE"
else
    echo "[Backup] Dumping via local pg_dump..."
    DB_URL="${SYNC_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/brightloop_subscriptions}"
    pg_dump "$DB_URL" --clean --if-exists > "$OUTPUT_FILE"
fi

if [ -f "$OUTPUT_FILE" ] && [ -s "$OUTPUT_FILE" ]; then
    SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE")
    echo "[Success] Backup created successfully!"
    echo "  Path: $OUTPUT_FILE"
    echo "  Size: $SIZE bytes"
else
    echo "[Error] Backup file is missing or empty." >&2
    exit 1
fi

