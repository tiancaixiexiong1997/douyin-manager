#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_FILE="${1:-}"
TARGET_DB="${2:-$ROOT_DIR/data/douyincehua.db}"

if [[ -z "$BACKUP_FILE" ]]; then
  echo "用法: $0 <backup_file(.db/.db.gz)> [target_db_path]" >&2
  exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "备份文件不存在: $BACKUP_FILE" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_DB")"

if [[ -f "$TARGET_DB" ]]; then
  SAFETY_COPY="${TARGET_DB}.before_restore.$(date +%Y%m%d_%H%M%S).bak"
  cp "$TARGET_DB" "$SAFETY_COPY"
  echo "已创建恢复前快照: $SAFETY_COPY"
fi

if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" > "$TARGET_DB"
else
  cp "$BACKUP_FILE" "$TARGET_DB"
fi

echo "恢复完成: $TARGET_DB"
