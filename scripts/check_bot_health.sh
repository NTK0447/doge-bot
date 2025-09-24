#!/bin/bash
set -euo pipefail
cd /root/docker-bot_stage4

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

notify() {
  local level="$1"; local msg="$2"
  msg="${msg//\"/\\\"}"
  if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
    curl -sS -m 5 -H "Content-Type: application/json" \
      -d "{\"content\":\"[BOT ${level}] ${msg}\"}" \
      "${DISCORD_WEBHOOK_URL}" >/dev/null || true
  fi
}

# 1) コンテナ稼働チェック
if ! docker compose ps --status running | grep -q 'doge-bot'; then
  notify "ERROR" "コンテナ doge-bot が停止しています。再起動を試みます。"
  docker compose up -d || true
fi

# 2) ログ更新チェック（15分以内に更新があるか）
today="logs/trades_$(date +%Y%m%d).csv"
if [ -f "$today" ]; then
  # mtime が 15分以内か
  if [ "$(find "$today" -mmin -15 2>/dev/null | wc -l)" -eq 0 ]; then
    notify "WARN" "今日のtradeログ更新が15分間ありません: $today"
  fi
else
  notify "WARN" "今日のtradeログが未生成です: $today"
fi
