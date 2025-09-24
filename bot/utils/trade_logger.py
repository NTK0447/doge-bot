# bot/utils/trade_logger.py
from __future__ import annotations
import csv
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

JST = timezone(timedelta(hours=9))


class TradeLogger:
    """
    取引ログを CSV へ追記し、仮想残高（balance_virtual）を内部管理する。

    - 2系統を同居：
      1) 日次集計用: logs/trades_YYYYMMDD.csv（log_trade / annotate）
         → ファイル名は UTC、timestamp は JST(+09:00)
      2) 生ログ(raw): 指定があれば csv_path（append / read_last）
         なければ logs/trades_raw_YYYYMMDD.csv に出力

    - order_executor からは append()/read_last() を使う想定
      （self.virtual_balance を read_last() で継承）
    """

    # 日次CSV（集計用）のヘッダ
    HEADER = [
        "timestamp", "symbol", "side", "qty",
        "entry", "exit", "fee", "pnl", "balance_virtual", "note"
    ]

    # RAWログ（生データ）のヘッダ（order_executor 互換）
    RAW_HEADER = ["ts", "symbol", "side", "qty", "price", "fee", "realized_pnl", "balance", "note"]

    def __init__(
        self,
        csv_path: Optional[str] = None,           # 指定があれば raw ログはこの単一ファイルへ
        logs_dir: str = "logs",                   # 指定がなければ logs_dir/ に日次rawを作る
        symbol: str = "DOGEUSDT",
        starting_balance: float = 50.0,           # 初期の仮想残高
    ):
        self.symbol = symbol
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)

        # 日次CSV（集計用）
        self.filepath = self._filepath_for_today()
        self._ensure_header()

        # RAWログ先の決定
        self.raw_path_fixed = csv_path
        # 仮想残高の初期化（raw→日次の順に引き継ぎを試みる）
        self.balance_virtual = self._load_last_balance_or_default(starting_balance)

    # ====== 日次CSV（集計用） ======

    def _filepath_for_today(self) -> str:
        # ファイル名は UTC ベース
        today = datetime.utcnow().strftime("%Y%m%d")
        return os.path.join(self.logs_dir, f"trades_{today}.csv")

    def _ensure_header(self) -> None:
        if not os.path.exists(self.filepath) or os.path.getsize(self.filepath) == 0:
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.HEADER)

    def _load_last_balance_or_default(self, default_balance: float) -> float:
        """
        raw（固定 or 日次）→ 日次集計 の順に balance を引き継ぐ。
        """
        raw_path = self._raw_path_for_today()

        # 1) RAW（固定）
        if self.raw_path_fixed and os.path.exists(self.raw_path_fixed):
            try:
                last = None
                with open(self.raw_path_fixed, "r") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        last = r
                if last and last.get("balance"):
                    return float(last["balance"])
            except Exception:
                pass

        # 2) RAW（日次）
        if not self.raw_path_fixed and os.path.exists(raw_path):
            try:
                last = None
                with open(raw_path, "r") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        last = r
                if last and last.get("balance"):
                    return float(last["balance"])
            except Exception:
                pass

        # 3) 日次集計
        if os.path.exists(self.filepath):
            try:
                last_balance = default_balance
                with open(self.filepath, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("balance_virtual"):
                            last_balance = float(row["balance_virtual"])
                return last_balance
            except Exception:
                return default_balance

        return default_balance

    def _jst_now(self) -> str:
        """JST(+09:00) のISO8601文字列を返す"""
        return datetime.now(JST).isoformat(timespec="seconds")

    def log_trade(
        self,
        side: str,
        qty: float,
        entry: float,
        exit: float,
        fee: float = 0.0,
        note: Optional[str] = None,
    ) -> None:
        """
        1トレード分を記録し、balance_virtual を更新して日次CSVへ追記。
        PnL計算はシンプル（手数料控除込み）。
        """
        if side not in ("Buy", "Sell"):
            raise ValueError("side must be 'Buy' or 'Sell'")

        # 方向別の損益（USDT評価）
        if side == "Buy":
            pnl = (exit - entry) * qty - fee
        else:
            pnl = (entry - exit) * qty - fee

        self.balance_virtual += pnl

        with open(self.filepath, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                self._jst_now(),
                self.symbol,
                side,
                qty,
                entry,
                exit,
                fee,
                pnl,
                self.balance_virtual,
                note or "",
            ])

    def annotate(self, note: str) -> None:
        """任意の注記行（pnl/balanceは空欄でメモだけ残す）"""
        with open(self.filepath, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                self._jst_now(),
                self.symbol, "", "", "", "", "", "", self.balance_virtual, note
            ])

    # ====== RAWログ（order_executor 互換） ======

    def _raw_path_for_today(self) -> str:
        if self.raw_path_fixed:
            return self.raw_path_fixed
        today = datetime.utcnow().strftime("%Y%m%d")
        return os.path.join(self.logs_dir, f"trades_raw_{today}.csv")

    def _ensure_raw_header(self) -> None:
        raw_path = self._raw_path_for_today()
        if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            with open(raw_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.RAW_HEADER)

    def append(self, row: Dict[str, Any]) -> None:
        """
        order_executor._log_trade() から呼ばれる互換API。
        受け取った dict をそのまま RAW CSV に落とす。
        期待キー: ts, symbol, side, qty, price, fee, realized_pnl, balance, note
        """
        self._ensure_raw_header()
        raw_path = self._raw_path_for_today()

        # --- JST変換 ---
        ts = row.get("ts", "")
        if ts:
            try:
                if isinstance(ts, (int, float)):  # UNIX timestamp
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(JST)
                else:  # ISO8601文字列
                    dt = datetime.fromisoformat(str(ts))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dt = dt.astimezone(JST)
                ts = dt.isoformat(timespec="seconds")
            except Exception:
                pass  # 失敗時は元のまま

        with open(raw_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                ts,
                row.get("symbol", ""),
                row.get("side", ""),
                row.get("qty", ""),
                row.get("price", ""),
                row.get("fee", ""),
                row.get("realized_pnl", ""),
                row.get("balance", ""),
                row.get("note", ""),
            ])

    def read_last(self) -> Optional[Dict[str, float]]:
        """
        order_executor 初期化時の仮想残高引き継ぎ用。
        まず RAW（固定 or 日次）を見て、無ければ日次CSVから balance を拾う。
        """
        # 1) RAW（固定 or 日次）
        for raw_path in [self.raw_path_fixed, (None if self.raw_path_fixed else self._raw_path_for_today())]:
            if raw_path and os.path.exists(raw_path):
                try:
                    last = None
                    with open(raw_path, "r") as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            last = r
                    if last and last.get("balance"):
                        return {"balance": float(last["balance"])}
                except Exception:
                    pass

        # 2) 日次集計（balance_virtual）
        if os.path.exists(self.filepath):
            try:
                last = None
                with open(self.filepath, "r") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        last = r
                if last and last.get("balance_virtual"):
                    return {"balance": float(last["balance_virtual"])}
            except Exception:
                pass

        # 3) 何も無ければ現在の内部状態
        return {"balance": float(self.balance_virtual)}
