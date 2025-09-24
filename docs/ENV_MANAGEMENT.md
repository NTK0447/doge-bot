# .env 運用ガイド（DOGE/USDT 自律型BOT）

本プロジェクトでは、**開発用** と **本番用** の `.env` を分離管理しています。  
これにより、開発効率・セキュリティ・バックアップ効率を両立させています。

---

## 1. 目的
- **開発環境** では最小限のパラメータで BOT の挙動確認を行う。
- **本番環境** では必要な API キーや通知設定を完全に揃え、安定稼働させる。
- 差分バックアップや Zip アーカイブに機密情報を混ぜない。

---

## 2. ファイル構成

```
docker-bot_stage4/
├─ .env               # 開発用（簡素化）
├─ env/
│   └─ .env           # 本番用（完全版）
├─ .env.example       # 参考用テンプレート
```

---

## 3. 開発用 `.env` （プロジェクト直下）

開発検証用に **必要最小限だけ** 残した設定。  
Docker コンテナ起動時に `dev.sh` で参照されます。

```env
# 開発用（簡素）
DRY_RUN=true
POLL_SEC=15

# テスト用のしきい値（必ずエントリーされる設定）
RSI_BUY_THRESHOLD=101
RSI_SELL_THRESHOLD=-1
DEPTH_IMB_THRESHOLD=-1.0
TAKER_BIAS_THRESHOLD=-1.0

ORDER_SIZE=100
SYMBOL=DOGEUSDT
```

---

## 4. 本番用 `.env` （`env/.env`）

本番稼働用に **完全な設定** を保持。  
systemd 経由で BOT を永続稼働させる際はこちらを参照します。

```env
# 本番用（完全）
BYBIT_API_KEY=xxxx
BYBIT_API_SECRET=yyyy

DISCORD_PATCH_WEBHOOK=https://discord.com/api/webhooks/...
DISCORD_SUMMARY_WEBHOOK=https://discord.com/api/webhooks/...

ORDER_SIZE=100
SYMBOL=DOGEUSDT

# 各戦略パラメータ
RSI_BUY_THRESHOLD=30
RSI_SELL_THRESHOLD=70
DEPTH_IMB_THRESHOLD=0.15
TAKER_BIAS_THRESHOLD=0.1

# Polling 間隔（秒）
POLL_SEC=15
```

---

## 5. 運用ルール

1. **分離管理**
   - 開発用はシンプル、本番用は完全。
   - それぞれ独立したファイルとして管理。

2. **差分バックアップ**
   - `nightly_patch_backup.sh` では `.env` も対象だが、開発用は軽量なのでノイズが少ない。
   - 本番用 `env/.env` は安全に保持（Zip化対象外）。

3. **切替運用**
   - 開発 → `bash dev.sh up`
   - 本番 → systemd サービスで `env/.env` を参照

---

## 6. 将来拡張（オプション）

- `env/.env.dev`, `env/.env.prod` と分け、`make dev` / `make prod` で切替。
- CI/CD パイプライン導入時に `.env` を暗号化（例: Ansible Vault, GitHub Secrets）。

---

## まとめ

- `.env` を **二系統に分ける** ことで、  
  - 開発効率 ✅  
  - セキュリティ ✅  
  - バックアップ効率 ✅  
  を同時に実現できた。  
