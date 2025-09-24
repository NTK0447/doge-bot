#!/usr/bin/env python3
import os
from pathlib import Path
import datetime as dt
import requests

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
DOCS = ROOT / "docs"

def load_env():
    env = {}
    env_file = ROOT / "env" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"): 
                continue
            if "=" in line:
                k,v = line.split("=",1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def extract_summary(log_file: Path, max_lines=2000):
    """
    とりあえず単純化した要約（後で強化可）
    - 最終 max_lines を読み込む
    - "TODO", "方針", "決定" のキーワードを拾う
    """
    lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
    summary = []
    for line in lines:
        if any(k in line for k in ("TODO","方針","決定","次回","振り返り","思いつき")):
            summary.append(line.strip())
    if not summary:
        summary = ["(要約対象のキーワードが見つかりませんでした)"]
    return "\n".join(summary)

def post_discord(webhook, content):
    try:
        resp = requests.post(webhook, json={"content": content}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠ Discord送信失敗: {e}")
        return False

def main():
    env = load_env()
    url = env.get("DISCORD_SUMMARY_WEBHOOK")
    if not url:
        print("⚠ DISCORD_SUMMARY_WEBHOOK が未設定です")
        return
    
    # 前日の会話ログ（仮: logs/conversation_YYYYMMDD.txt）
    yesterday = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
    log_file = LOGS / f"conversation_{yesterday}.txt"
    if not log_file.exists():
        print(f"⚠ ログファイルが見つかりません: {log_file}")
        return
    
    summary = extract_summary(log_file)
    title = f"📝 {yesterday} 振り返りサマリ"
    content = f"**{title}**\n```\n{summary}\n```"
    
    if post_discord(url, content):
        print(f"✅ Discordへ送信完了: {title}")

if __name__ == "__main__":
    main()
