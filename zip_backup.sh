#!/usr/bin/env bash
set -euo pipefail

# === Settings ===
PROJECT_DIR="${PROJECT_DIR:-$HOME/docker-bot_stage4}"
OUT_DIR="${OUT_DIR:-$HOME}"                 # 既定の出力先（~ に保存）
WITH_LOGS="${WITH_LOGS:-false}"             # true にすると logs/ も含める
TS="$(date +%Y%m%d_%H%M)"
ZIP_NAME="doge-bot_backup_${TS}.zip"
ZIP_PATH="${OUT_DIR}/${ZIP_NAME}"

# --- 引数処理 ---
# 例:  WITH_LOGS=true OUT_DIR=~/backups bash zip_backup.sh
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-logs) WITH_LOGS=true; shift ;;
    --out) OUT_DIR="${2:-$OUT_DIR}"; shift 2 ;;
    --project) PROJECT_DIR="${2:-$PROJECT_DIR}"; shift 2 ;;
    -h|--help)
      cat <<EOF
Usage: [ENV=VALUE ...] bash zip_backup.sh [--with-logs] [--out PATH] [--project PATH]

ENV:
  WITH_LOGS=true|false    logs/ を含める（既定: false）
  OUT_DIR=PATH            出力先ディレクトリ（既定: \$HOME）
  PROJECT_DIR=PATH        プロジェクトルート（既定: \$HOME/docker-bot_stage4）
EOF
      exit 0 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# --- 事前チェック ---
command -v zip >/dev/null 2>&1 || { echo "zip が未インストールです: apt-get install -y zip"; exit 1; }
[[ -d "$PROJECT_DIR" ]] || { echo "PROJECT_DIR 不正: $PROJECT_DIR"; exit 1; }
mkdir -p "$OUT_DIR"

echo "📦 Backup start"
echo "  Project : $PROJECT_DIR"
echo "  Output  : $ZIP_PATH"
echo "  With logs: $WITH_LOGS"

cd "$PROJECT_DIR"

# --- 除外パターン ---
# * 仮想環境やキャッシュ、IDE/OSファイル、巨大なビルド成果物は除外
EXCLUDES=(
  "-x" "*/.venv/*"
  "-x" "*/venv/*"
  "-x" "*/__pycache__/*"
  "-x" "*.pyc" "-x" "*.pyo"
  "-x" "*/.mypy_cache/*"
  "-x" "*/.pytest_cache/*"
  "-x" "*/.ipynb_checkpoints/*"
  "-x" ".git/*" "-x" ".gitignore"
  "-x" ".DS_Store"
  "-x" "*/.idea/*" "-x" "*/.vscode/*"
  # Docker 実行時にできる不要物
  "-x" "*/.cache/*"
  "-x" "*/__workdir__/*"
)

# logs/ を含めないのがデフォルト（重くなるため）
if [[ "$WITH_LOGS" != "true" ]]; then
  EXCLUDES+=("-x" "logs/*")
fi

# --- 必須含有物の存在チェック（警告のみ） ---
REQUIRED=( "Dockerfile" "docker-compose.yml" "requirements.txt" "env/.env" "bot" "main.py" )
for f in "${REQUIRED[@]}"; do
  [[ -e "$f" ]] || echo "⚠️  注意: $f が見つかりません（存在しない場合は無視可）"
done

# --- Zip 化 ---
# プロジェクト内の相対パスで固める（解凍時に展開しやすくする）
TMP_LIST=( . )
echo "🗜  Creating zip…"
zip -r "$ZIP_PATH" "${TMP_LIST[@]}" "${EXCLUDES[@]}" >/dev/null

# 完了表示
SIZE_HUMAN="$(du -h "$ZIP_PATH" | awk '{print $1}')"
echo "✅ Done: $ZIP_PATH  (size: $SIZE_HUMAN)"
echo "💡 ダウンロード例（Mac/iOS/MacBook）："
echo "scp -i ~/.ssh/Mac.pem root@<VPS_IP>:${ZIP_PATH} ~/Downloads/"

# 終了
exit 0
