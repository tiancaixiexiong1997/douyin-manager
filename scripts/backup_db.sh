#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_FILE="${1:-$ROOT_DIR/data/douyincehua.db}"
BACKUP_DIR="${2:-$ROOT_DIR/backups}"
RETENTION_DAYS="${3:-${BACKUP_RETENTION_DAYS:-14}}"

if [[ ! -f "$DB_FILE" ]]; then
  echo "数据库文件不存在: $DB_FILE" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="$BACKUP_DIR/douyincehua_${STAMP}.db.gz"

TMP_COPY="$BACKUP_DIR/.douyincehua_${STAMP}.tmp.db"
cp "$DB_FILE" "$TMP_COPY"
gzip -c "$TMP_COPY" > "$TARGET"
rm -f "$TMP_COPY"

echo "备份完成: $TARGET"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && [[ "$RETENTION_DAYS" -gt 0 ]]; then
  # 清理超过保留天数的历史备份，防止磁盘被长期占满。
  CLEANUP_LOG="$(mktemp)"
  find "$BACKUP_DIR" -type f -name 'douyincehua_*.db.gz' -mtime +"$RETENTION_DAYS" -print -delete >"$CLEANUP_LOG" || true
  CLEANUP_COUNT="$(wc -l < "$CLEANUP_LOG" | tr -d ' ')"
  rm -f "$CLEANUP_LOG"
  echo "历史备份清理完成: 删除 $CLEANUP_COUNT 个 (保留天数: $RETENTION_DAYS)"
fi
