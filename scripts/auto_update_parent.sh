#!/bin/bash
set -euo pipefail
cd /root/docker-bot_stage4

# .env から DISCORD_WEBHOOK_URL を読み取り（なければ空のまま）
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

notify() {
  local level="$1"    # INFO / ERROR
  local msg="$2"
  # 簡易エスケープ
  msg="${msg//\"/\\\"}"
  if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -sS -m 5 -H "Content-Type: application/json" \
      -d "{\"content\":\"[${level}] ${msg}\"}" \
      "${DISCORD_WEBHOOK_URL}" >/dev/null || true
  fi
}

# 親ビュー生成（失敗時は systemd に非ゼロで返す）
if python3 scripts/generate_parent_view.py; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 親ビュー更新済み" >> logs/parent_update.log
  notify "INFO" "ParentView 更新成功: docs/PARENT_VIEW.md を再生成しました。"
else
  notify "ERROR" "ParentView 更新失敗: generate_parent_view.py がエラー終了。"
  exit 1
fi
