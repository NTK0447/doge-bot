#!/bin/bash
set -e

# 📁 同期元のマスターファイルがあるパス
SRC_DIR=/root/doge-bot_stage4

# 📁 このスクリプトがある作業ディレクトリ
DEST_DIR=$(dirname "$0")

echo "🧹 .env の同期中..."
cp "$SRC_DIR/.env" "$DEST_DIR/.env"

echo "📦 requirements.txt の同期中..."
cp "$SRC_DIR/requirements.txt" "$DEST_DIR/requirements.txt"

echo "🐳 Docker イメージをビルド中..."
docker compose build

echo "✅ ビルド完了！"
