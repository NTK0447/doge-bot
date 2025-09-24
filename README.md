# DOGE/USDT 自律進化型BOT

**目的**: 「安定運用 × 自律進化」を両立する現物/先物向け自動売買 BOT  
**稼働環境**: VPS (Docker + systemd), GitHub Actions による検証・通知, Discord 連携

---

## 1. プロジェクト概要
- 対象: Bybit の DOGEUSDT 無期限
- 戦略: 逆張りベース (S4) で板/テープ/テクニカルの特徴量を拡張。S5 で LinUCB セレクタ
- 運用: Nightly バックアップ (FULL/SHARED) ＋手動差分配布 (MANUAL)
- **Source of Truth**: 最新の **nightly 差分 zip**(SHARED) と `roadmap.yaml`

---

## 2. 開発指針
- **安定重視**: 暴走抑止、部分約定追撃、サーキットブレーカを必須装備
- **実装優先度**: 戦略・実行制御・ログ・特徴量を「セット」で改修 (横断整合を最優先)
- **進行管理**: nightly 差分 zip (SHARED) で共有し、GitHub で妥当性を検証
- **自律性**: 成績からのパラメータ提案・戦略の命題管理を段階導入

---

## 3. ステージ進行ロードマップ（詳細版）

### ✅ Stage1〜3: 基盤安定化
- 暴走抑止: MAX_OPEN_ORDERS / POSITION_COOLDOWN_SEC / ピラミッド制御
- 部分約定追撃: IOC 再注文・スリッページ段階拡大
- サーキットブレーカ V2: 急変検知＋逆方向強制クールダウン

### 🚧 Stage4: WSベースの特徴量拡張（現在地）
- 板/テープ/テクニカル統合
- features.py: `spread_bps`, `depth_imbalance`, `taker_imbalance`, `momentum_1s/5s`
- indicators.py: `RSI/BB/ATR` の整備
- core.py: WS整合, 特徴量取得ループ, 戦略呼び出し注入
- strategy01.py: 逆張り系 / 指値ブレイク / 加速ロジック, note ログ強化
- trade_logger.py: 日次集計 (JST) + RAW ログ (互換 API) + 仮想残高継承
- Discord 通知: 約定/発注/戦略ログ/正否判定

### 🔜 Stage5: LinUCB 戦略セレクタ
- 特徴量 (①〜④, 将来追加可) を並列評価し、**LinUCB** で注文選択
- 報酬設計: スプレッド, 板厚, 成約方向, RSI/BB, モメンタム等
- 目的: 短期の安定 PnL (右上化)

### 🔮 Stage6: 並列戦略・自動チューニング
- 戦略の多重テスト (PF/勝率/ドローダウン) ⇒ 凍結/復活
- 自己学習型進化 (報酬関数ベース) を自動化し Discord へ

### 🧠 Stage7〜8: スケール/自律進化
- マルチ銘柄 & マルチインスタンス
- 日次 PDF レポート化と CI/CD 的自動反映
- 神モード (完全自律進化) による自己進化

---

## 4. 技術スタック
- Python 3.11 / pybit v5 (Bybit REST/WS)
- Docker / docker-compose / systemd (監視・再起動)
- GitHub Actions (manifest/summary/unmapped の整合チェック＋Discord 通知)
- Discord Webhook (運用/アラート)

---

## 5. セットアップ

### 5.1 依存準備
```bash
# 環境変数
cp .env.example env/.env  
# (APIキーや Webhook は env/.env に設定)

# Docker ビルド・起動
docker compose build
docker compose up -d
```

### 5.2 systemd (Nightly 実行)
`/etc/systemd/system/nightly_patch_backup.service`
```ini
[Unit]
Description=Nightly Patch Backup (FULL + SHARED)
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/root/docker-bot_stage4
ExecStart=/root/docker-bot_stage4/scripts/nightly_patch_backup.sh
StandardOutput=append:/root/docker-bot_stage4/logs/nightly_patch.log
StandardError=append:/root/docker-bot_stage4/logs/nightly_patch.log
```

`/etc/systemd/system/nightly_patch_backup.timer`
```ini
[Unit]
Description=Run Nightly Patch Backup at JST 0:05

[Timer]
OnCalendar=*-*-* 15:05:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

---

## 6. 運用フロー

### 6.1 Nightly (自動)
- FULL.zip + SHARED.zip を backups/ に生成
- Discord (FULL/SHARED) へ添付通知
- GitHub には SHARED (軽量差分) だけ push (本体 README/コードの変更も同時に push)
- 7日超の古いバックアップは自動クリーン

### 6.2 Manual (手動配布)
```bash
# 共有用の軽量差分だけを作って即連携
bash scripts/nightly_patch_backup.sh --manual
```
- SHARED.zip (軽量差分) のみ生成 → Discord & GitHub (軽量だけ)
- 巨大ファイルを消してレポジトリ直下に置かない (.git が肥大化します)

---

## 7. GitHub Actions (整合チェック & Discord 通知)
- ワークフロー: `.github/workflows/zip_check.yml`
- 内容:
  - compare_zip_repo.py の実行 → 失敗時はログ要約を Discord に通知
  - 成功/失敗いずれも結果を送信
- 秘密管理: `DISCORD_WEBHOOK_ZIPCHECK` (リポジトリ Secrets)

---

## 8. 環境変数 (env/.env 抜粋)
```ini
# 通知
DISCORD_PATCH_WEBHOOK_FULL=...
DISCORD_PATCH_WEBHOOK_SHARED=...
DISCORD_WEBHOOK_ZIPCHECK=...

# 動作
LOG_LEVEL=INFO
DRY_RUN=false
POLL_SEC=15
LEVERAGE=50

# 暴走抑止
MAX_OPEN_ORDERS=3
POSITION_COOLDOWN_SEC=30
ALLOW_PYRAMID=false
NET_CAP=2000

# 追撃設定
RETRY_UNFILLED_ORDER=3
LIMIT_SLIPPAGE_PCT=0.05

# サーキットブレーカ
CB_THRESHOLD_PCT=1.5
CB_LOOKBACK_SEC=10

# 戦略パラメータ (S4〜)
RSI_PERIOD=14
SMA_FAST=9
SMA_SLOW=21
BBANDS_PERIOD=20
BBANDS_STDDEV=2
ATR_PERIOD=14
TP_PCT=1.0
SL_PCT=0.8

INTERVAL=1
SYMBOL=DOGEUSDT
```

---

## 9. リポジトリ衛生 (大事)
- `.gitignore` で project_patch_*.zip を必ず除外
- リポジトリ直下に zip を置かない (GitHub 100MB 制限 & 履歴肥大の原因)
- 大容量を push してしまった場合は git filter-repo で完全除去し、強制 push

---

## 10. 主要ファイル
- bot/core.py … 戦略呼び出し, 特徴量供給, ポジ同期
- bot/features/features.py … 板/テープ由来の高頻特徴量
- bot/features/indicators.py … OHLCV 系インジケータ
- bot/strategies/strategy01.py … 逆張り系の基準戦略 (S4 対応)
- bot/utils/order_executor.py … 発注・約定ハンドリング
- bot/utils/position_handler.py … 内部/実ポジの整合
- bot/utils/trade_logger.py … 日次集計＋RAW ログ, 仮想残高継承
- scripts/nightly_patch_backup.sh … FULL/SHARED 生成・通知・push

---

## 11. 神モード (将来構想)
- 自己学習セレクタ: LinUCB → RL で戦略選択を自動最適化
- 寿命管理: スコア関数で凍結/復帰の自動化
- 自動チューニング: 成績に基づく .env 提案・適用
- 自己進化: テスト戦略の自然選択 (勝率の分布定着)

---

## 12. よくあるハマりどころ
- Discord 413 → zip が大きすぎ。SHARED の exclude 見直し or 差分粒度を調整
- Git push 100MB 超過 → zip を絶対にリポジトリ直下に置かない
- Actions が「常に成功」→ compare_zip_repo.py の sys.exit(1) を確認
- JST/Scheduler → .timer は UTC 15:05 が JST 0:05

---

## 13. ライセンス
MIT (予定)

---

### 次の手順 (超短縮)
```bash
# 置き換え
nano README.md   # ← 上記を貼り付けて保存

# 反映
git add README.md
git commit -m "docs: expand roadmap and ops details"
git push origin main
```
