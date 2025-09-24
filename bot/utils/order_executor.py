# bot/utils/order_executor.py
from __future__ import annotations
from datetime import datetime

try:
    from bot.utils.trade_logger import TradeLogger
except Exception:
    TradeLogger = None


class OrderExecutor:
    """
    - 戦略からの signal を実行
    - エントリー時に推定手数料をバッファ保存し、クローズ時に往復手数料を合算
    - DRY_RUN では発注はせず、日次CSVとRAWログの両方に書き込み
    signal 例: {"side": "Buy"|"Sell", "qty": 100, "price": 0.1234(optional), "note": "...", "maker": bool}
    """
    def __init__(self, exchange, config, logger=None, discord=None):
        self.exchange = exchange
        self.config = config
        self.logger = logger
        self.discord = discord

        if self.logger is None:
            import logging
            self.logger = logging.getLogger(__name__)

        self.symbol = getattr(config, "SYMBOL", "DOGEUSDT")
        self.is_dry = str(getattr(config, "DRY_RUN", "true")).lower() == "true"

        # 手数料（テイカー/メイカー）
        self.taker_fee_pct = float(getattr(config, "TAKER_FEE_PCT", 0.0006))
        self.maker_fee_pct = float(getattr(config, "MAKER_FEE_PCT", 0.0002))

        # TradeLogger 初期化
        if TradeLogger is None:
            self.logger.warning("[TradeLogger] import failed (module not found)")
            self.tlog = None
        else:
            try:
                logs_dir = getattr(config, "TRADE_LOG_DIR", "logs")
                start_bal = float(getattr(config, "VIRTUAL_BALANCE_USDT", 100.0))
                self.tlog = TradeLogger(logs_dir=logs_dir, symbol=self.symbol, starting_balance=start_bal)
                self.logger.info(f"[TradeLogger] enabled: daily CSV => {self.tlog.filepath}")
            except Exception as e:
                self.logger.warning(f"[TradeLogger] disabled: {e!r}")
                self.tlog = None

        # --- エントリースナップショット（単一ポジ軽量版） ---
        self._entry_snapshot = None

    # ------------ 価格取得フォールバック ------------
    def _get_mark_price(self) -> float:
        try:
            lp = float(self.exchange.get_last_price())
            if lp > 0:
                return lp
        except Exception:
            pass
        try:
            ob = self.exchange.get_orderbook()
            if isinstance(ob, dict):
                if "best_bid" in ob and "best_ask" in ob:
                    bb = float(ob.get("best_bid") or 0)
                    ba = float(ob.get("best_ask") or 0)
                    if bb > 0 and ba > 0:
                        return (bb + ba) / 2.0
                bids = ob.get("bids") or []
                asks = ob.get("asks") or []
                if bids and asks and bids[0] and asks[0]:
                    bb = float(bids[0][0])
                    ba = float(asks[0][0])
                    if bb > 0 and ba > 0:
                        return (bb + ba) / 2.0
        except Exception:
            pass
        return 0.0

    def _compute_fee(self, price: float, qty: float, is_maker: bool) -> float:
        fee_pct = self.maker_fee_pct if is_maker else self.taker_fee_pct
        return price * qty * fee_pct

    # ------------ エントリー ------------
    def execute(self, signal: dict):
        side = signal["side"]
        qty = float(signal["qty"])
        price = float(signal.get("price") or self._get_mark_price())
        note = signal.get("note", "")
        is_maker = bool(signal.get("maker", False))

        if price <= 0:
            self.logger.error("Price not available. Abort.")
            return

        fee_entry = self._compute_fee(price, qty, is_maker=is_maker)

        # スナップショット保存
        self._entry_snapshot = {
            "side": side, "qty": qty, "price": price,
            "fee": fee_entry, "maker": is_maker,
        }

        if self.is_dry:
            self.logger.info(
                f"DRY_RUN: Would place {side} {qty} {self.symbol} @ {price} (entry_fee≈{fee_entry:.6f})"
            )
            if self.tlog:
                note_full = f"OPEN {side} qty={qty} @ {price} entry_fee≈{fee_entry:.6f} {note}"
                # 日次CSV
                self.tlog.annotate(note_full)
                # RAWログ
                self.tlog.append({
                    "ts": datetime.utcnow().isoformat(timespec="seconds"),
                    "symbol": self.symbol, "side": side, "qty": qty,
                    "price": price, "fee": fee_entry, "realized_pnl": 0.0,
                    "balance": self.tlog.balance_virtual, "note": note_full,
                })
                self.logger.info(f"[TradeLogger] wrote DRY_RUN entry to {self.tlog.filepath}")
            return

        # 実発注
        try:
            self.exchange.place_market_order(side=side, qty=qty)
            self.logger.info(f"✅ Placed {side} {qty} {self.symbol} @ ~{price}")
            if self.tlog:
                self.tlog.annotate(f"OPEN {side} qty={qty} @ {price} entry_fee≈{fee_entry:.6f} {note}")
        except Exception as e:
            self.logger.error(f"❌ Order failed: {e}")
            if self.discord:
                self.discord.send(f"❌ Order failed: {e}")

    # ------------ クローズ ------------
    def close_position(self, position: dict, reason: str = "close"):
        if not position or float(position.get("size", 0) or 0) == 0:
            self.logger.info("No open position.")
            return

        side_entry = position["side"]
        qty = float(position["size"])
        entry = float(position["entry_price"])
        side_close = "Sell" if side_entry == "Buy" else "Buy"

        exit_price = float(self._get_mark_price())
        if exit_price <= 0:
            self.logger.error("Close price not available. Abort.")
            return

        # 手数料
        fee_close = self._compute_fee(exit_price, qty, is_maker=False)
        fee_entry = self._entry_snapshot.get("fee", 0.0) if self._entry_snapshot else 0.0
        fee_roundtrip = fee_entry + fee_close

        # 損益計算
        if side_entry == "Buy":
            pnl_gross = (exit_price - entry) * qty
        else:
            pnl_gross = (entry - exit_price) * qty
        realized_pnl = pnl_gross - fee_roundtrip

        if self.is_dry:
            if self.tlog:
                note_full = f"DRY_RUN {reason} (entry_fee+close_fee)"
                # 日次CSV
                self.tlog.log_trade(
                    side=side_entry, qty=qty, entry=entry, exit=exit_price,
                    fee=fee_roundtrip, note=note_full
                )
                # RAWログ
                self.tlog.append({
                    "ts": datetime.utcnow().isoformat(timespec="seconds"),
                    "symbol": self.symbol, "side": side_entry, "qty": qty,
                    "price": exit_price, "fee": fee_roundtrip,
                    "realized_pnl": realized_pnl,
                    "balance": self.tlog.balance_virtual, "note": note_full,
                })
                self.logger.info(f"[TradeLogger] wrote DRY_RUN close to {self.tlog.filepath}")
            self.logger.info(
                f"DRY_RUN: Would close {side_entry} {qty} {self.symbol} @ {exit_price} "
                f"(entry {entry}) pnl≈{realized_pnl:.6f} (fees≈{fee_roundtrip:.6f})"
            )
            self._entry_snapshot = None
            return

        # 実発注
        try:
            self.exchange.place_market_order(side=side_close, qty=qty)
            if self.tlog:
                self.tlog.log_trade(
                    side=side_entry, qty=qty, entry=entry, exit=exit_price,
                    fee=fee_roundtrip, note=reason
                )
            self.logger.info(
                f"✅ Closed {side_entry} {qty} {self.symbol} @ ~{exit_price} "
                f"(pnl≈{realized_pnl:.6f}, fees≈{fee_roundtrip:.6f})"
            )
            if self.discord:
                self.discord.send(
                    f"✅ Closed {side_entry} {qty} {self.symbol} @ ~{exit_price} (entry {entry}) "
                    f"PNL≈{realized_pnl:.6f} (fees≈{fee_roundtrip:.6f}) [{reason}]"
                )
        except Exception as e:
            self.logger.error(f"❌ Close failed: {e}")
            if self.discord:
                self.discord.send(f"❌ Close failed: {e}")
        finally:
            self._entry_snapshot = None
