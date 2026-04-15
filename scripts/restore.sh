#!/usr/bin/env bash
set -euo pipefail
# BearSub restore script
# Usage: ./scripts/restore.sh <db_backup.db> [subs_backup.tar.gz]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

DB_PATH="${DB_PATH:-$PROJECT_ROOT/data/db/subtitles.db}"
SUBS_DIR="${SUBS_DIR:-$PROJECT_ROOT/data/subs}"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <db_backup.db> [subs_backup.tar.gz]"
    exit 1
fi

DB_BACKUP="$1"
SUBS_BACKUP="${2:-}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting BearSub restore..."

# Restore database
if [[ -f "$DB_BACKUP" ]]; then
    mkdir -p "$(dirname "$DB_PATH")"
    cp "$DB_BACKUP" "$DB_PATH"
    echo "Database restored from: $DB_BACKUP"
else
    echo "ERROR: DB backup not found: $DB_BACKUP"
    exit 1
fi

# Restore subs
if [[ -n "$SUBS_BACKUP" ]]; then
    if [[ -f "$SUBS_BACKUP" ]]; then
        mkdir -p "$(dirname "$SUBS_DIR")"
        tar -xzf "$SUBS_BACKUP" -C "$(dirname "$SUBS_DIR")"
        echo "Subtitles restored from: $SUBS_BACKUP"
    else
        echo "ERROR: Subs backup not found: $SUBS_BACKUP"
        exit 1
    fi
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Restore complete."
