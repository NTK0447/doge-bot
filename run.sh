#!/bin/bash
# run.sh - Docker Compose 簡易起動スクリプト

set -e  # エラーが出たら止める

echo "🐳 DOGE BOT 再ビルド & 起動中...（Ctrl+Cで停止）"

# 1) ビルド
docker compose build

# 2) 起動（バックグラウンドで）
docker compose up -d

# 3) 稼働確認
echo ""
echo "🚀 コンテナ一覧:"
docker compose ps

# 4) ログ追跡（Ctrl+Cで停止）
echo ""
echo "📜 ログをフォロー中..."
docker compose logs -f --tail=50
