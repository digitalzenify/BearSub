#!/usr/bin/env bash
set -euo pipefail
# BearSub backup script
# Usage: ./scripts/backup.sh [backup_dir]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

BACKUP_DIR="${1:-${BACKUP_DIR:-$PROJECT_ROOT/backups}}"
DB_PATH="${DB_PATH:-$PROJECT_ROOT/data/db/subtitles.db}"
SUBS_DIR="${SUBS_DIR:-$PROJECT_ROOT/data/subs}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting BearSub backup..."

# Backup SQLite DB
if [[ -f "$DB_PATH" ]]; then
    DB_BACKUP="$BACKUP_DIR/subtitles_${TIMESTAMP}.db"
    cp "$DB_PATH" "$DB_BACKUP"
    echo "Database backed up: $DB_BACKUP"
else
    echo "WARNING: Database not found at $DB_PATH"
fi

# Backup subs directory
if [[ -d "$SUBS_DIR" ]]; then
    SUBS_BACKUP="$BACKUP_DIR/subs_${TIMESTAMP}.tar.gz"
    tar -czf "$SUBS_BACKUP" -C "$(dirname "$SUBS_DIR")" "$(basename "$SUBS_DIR")"
    echo "Subtitles backed up: $SUBS_BACKUP"
else
    echo "WARNING: Subs directory not found at $SUBS_DIR"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup complete."
