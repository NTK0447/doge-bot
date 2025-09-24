#!/bin/bash
# scripts/nightly_patch_backup.sh
set -euo pipefail

BASE_DIR="/root/docker-bot_stage4"
BACKUP_DIR="$BASE_DIR/backups"
DATE_JST=$(date +'%Y%m%d' -d '+9 hours')

# Load env vars
if [ -f "$BASE_DIR/env/.env" ]; then
  set -a; . "$BASE_DIR/env/.env"; set +a
elif [ -f "$BASE_DIR/.env" ]; then
  set -a; . "$BASE_DIR/.env"; set +a
fi

# Paths
ZIP_FULL="$BACKUP_DIR/project_patch_full_${DATE_JST}.zip"
ZIP_SHARED="$BACKUP_DIR/project_patch_shared_${DATE_JST}.zip"
MANIFEST_FULL="$BACKUP_DIR/manifest_full_${DATE_JST}.txt"
MANIFEST_SHARED="$BACKUP_DIR/manifest_shared_${DATE_JST}.txt"
UNMAPPED_FULL="$BACKUP_DIR/unmapped_full_${DATE_JST}.txt"
UNMAPPED_SHARED="$BACKUP_DIR/unmapped_shared_${DATE_JST}.txt"
SUMMARY_FULL="$BACKUP_DIR/summary_full_${DATE_JST}.txt"
SUMMARY_SHARED="$BACKUP_DIR/summary_shared_${DATE_JST}.txt"

DISCORD_WEBHOOK_FULL="${DISCORD_PATCH_WEBHOOK_FULL:-}"
DISCORD_WEBHOOK_SHARED="${DISCORD_PATCH_WEBHOOK_SHARED:-}"
DISABLE_GIT_PUSH="${DISABLE_GIT_PUSH:-false}"

mkdir -p "$BACKUP_DIR"
cd "$BASE_DIR"

# ------------------------------
# Functions
# ------------------------------

make_manifest_and_zip() {
  local mode="$1" manifest_file="$2" zip_file="$3" exclude_env="$4"

  echo "[*] Generating manifest ($mode)..."
  if [ "$exclude_env" = "true" ]; then
    find . -type f \
      ! -path "./venv/*" ! -path "./__pycache__/*" \
      ! -path "./.git/*" ! -path "./backups/*" ! -path "./logs/*" \
      ! -name "patch_*.txt" ! -name "*.log" ! -name "*.pyc" \
      ! -name ".env" ! -path "./env/.env" \
      | sort > "$manifest_file"
  else
    find . -type f \
      ! -path "./venv/*" ! -path "./__pycache__/*" \
      ! -path "./.git/*" ! -path "./backups/*" ! -path "./logs/*" \
      ! -name "patch_*.txt" ! -name "*.log" ! -name "*.pyc" \
      | sort > "$manifest_file"
  fi

  echo "[*] Creating zip archive ($mode)..."
  if [ "$exclude_env" = "true" ]; then
    zip -rq "$zip_file" . \
      -x "venv/*" "__pycache__/*" ".git/*" "*.log" "*.pyc" \
         "backups/*" "logs/*" "patch_*.txt" ".env" "env/.env"
  else
    zip -rq "$zip_file" . \
      -x "venv/*" "__pycache__/*" ".git/*" "*.log" "*.pyc" \
         "backups/*" "logs/*" "patch_*.txt"
  fi

  echo "[*] Checking env files in archive ($mode)..."
  zipinfo -1 "$zip_file" | grep -E "(\.env|\.env\.example)" || \
    echo "⚠️ No env/.env/.env.example files found in archive ($mode)"
}

calc_summary() {
  local mode="$1" manifest_file="$2" summary_file="$3"
  local prev_manifest="$BACKUP_DIR/manifest_${mode}_prev.txt"
  local diff_file="$BACKUP_DIR/diff_${mode}_${DATE_JST}.txt"

  if [ -f "$prev_manifest" ]; then
    diff "$prev_manifest" "$manifest_file" > "$diff_file" || true
    local NEW=$(grep '^>' "$diff_file" | wc -l | tr -d '[:space:]')
    local DEL=$(grep '^<' "$diff_file" | wc -l | tr -d '[:space:]')
    local CHG=$(( NEW + DEL ))

    {
      echo "📊 ${mode} Summary ${DATE_JST}"
      echo "変更ファイル数: ${CHG}（新規: ${NEW}, 削除: ${DEL}）"
      echo "比較: $(basename "$prev_manifest") → $(basename "$manifest_file")"
    } > "$summary_file"
  else
    {
      echo "📊 ${mode} Summary ${DATE_JST}"
      echo "初回実行のため比較対象なし"
    } > "$summary_file"
  fi

  cp -f "$manifest_file" "$prev_manifest"
}

run_unmapped_check() {
  local manifest_file="$1" unmapped_file="$2"
  python3 - << 'PYCODE' "$manifest_file" "$BASE_DIR/roadmap.yaml" "$unmapped_file"
import sys, yaml
manifest_file, roadmap_file, unmapped_file = sys.argv[1:]
with open(manifest_file) as f:
    manifest = [line.strip().lstrip("./") for line in f if line.strip()]
with open(roadmap_file) as f:
    roadmap = yaml.safe_load(f)

roadmap_files = set()
for stage in roadmap.get("stages", []) or []:
    for task in stage.get("tasks") or []:
        for p in (task.get("target_files") or []):
            roadmap_files.add(str(p))
for bundle in roadmap.get("bundles", []) or []:
    for p in (bundle.get("files") or []):
        roadmap_files.add(str(p))

manifest_files = set(manifest)
unmapped = [p for p in manifest_files if not any(key in p for key in roadmap_files)]

with open(unmapped_file, "w") as out:
    if unmapped:
        out.write("\n".join(unmapped))
PYCODE
}

post_to_discord() {
  local mode="$1" zip_file="$2" manifest_file="$3" unmapped_file="$4" summary_file="$5" webhook_url="$6"
  if [ -z "$webhook_url" ]; then
    echo "⚠️ Webhook for $mode not set. Skipping."
    return 0
  fi
  echo "[*] Sending ${mode} to Discord..."
  HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" \
    -F "file1=@${zip_file}" \
    -F "file2=@${manifest_file}" \
    -F "file3=@${unmapped_file}" \
    -F "file4=@${summary_file}" \
    -F "payload_json={\"content\":\"📦 Nightly Patch ${mode} ${DATE_JST}\"}" \
    "${webhook_url}" )
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
    echo "✅ ${mode} notification sent, HTTP ${HTTP_CODE}"
  else
    echo "❌ ${mode} notification failed, HTTP ${HTTP_CODE}"
  fi
}

# ------------------------------
# Main Run
# ------------------------------
make_manifest_and_zip "FULL"   "$MANIFEST_FULL"   "$ZIP_FULL"   "false"
calc_summary         "FULL"   "$MANIFEST_FULL"   "$SUMMARY_FULL"
run_unmapped_check   "$MANIFEST_FULL"            "$UNMAPPED_FULL"

make_manifest_and_zip "SHARED" "$MANIFEST_SHARED" "$ZIP_SHARED" "true"
calc_summary         "SHARED" "$MANIFEST_SHARED" "$SUMMARY_SHARED"
run_unmapped_check   "$MANIFEST_SHARED"          "$UNMAPPED_SHARED"

post_to_discord "FULL"   "$ZIP_FULL"   "$MANIFEST_FULL"   "$UNMAPPED_FULL"   "$SUMMARY_FULL"   "$DISCORD_WEBHOOK_FULL" || true
post_to_discord "SHARED" "$ZIP_SHARED" "$MANIFEST_SHARED" "$UNMAPPED_SHARED" "$SUMMARY_SHARED" "$DISCORD_WEBHOOK_SHARED" || true

# ------------------------------
# GitHub Push Integration
# ------------------------------
if [ "$DISABLE_GIT_PUSH" != "true" ]; then
  echo "[*] GitHub push start..."
  cp "$ZIP_SHARED" "$BASE_DIR/"  # リポジトリ直下に最新SHARED zipをコピー
  git -C "$BASE_DIR" add "project_patch_shared_${DATE_JST}.zip"
  git -C "$BASE_DIR" commit -m "Nightly shared patch ${DATE_JST}" || echo "No changes to commit."
  git -C "$BASE_DIR" push origin main || echo "⚠️ Git push failed."
else
  echo "[*] GitHub push skipped (DISABLE_GIT_PUSH=true)"
fi

echo "[*] Done."
