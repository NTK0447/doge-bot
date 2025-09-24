# bot/strategies/strategy01.py
from __future__ import annotations
import logging

class Strategy01:
    """
    RSI + 板厚バランス + 成行バイアス を利用したシンプル戦略
      - 未保有: RSIと特徴量条件を満たせばエントリー
      - 保有:   RSIによるクローズ判定
    """

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger or logging.getLogger("DogeBot")

        # --- RSIしきい値 ---
        self.buy_th  = float(getattr(config, "RSI_BUY_THRESHOLD", 20))
        self.sell_th = float(getattr(config, "RSI_SELL_THRESHOLD", 80))
        self.exit_long  = float(getattr(config, "RSI_EXIT_LONG", 55))
        self.exit_short = float(getattr(config, "RSI_EXIT_SHORT", 45))

        # --- 板厚/成行偏りしきい値（Stage4追加） ---
        self.depth_thr = float(getattr(config, "DEPTH_IMB_THRESHOLD", 0.15))
        self.taker_thr = float(getattr(config, "TAKER_BIAS_THRESHOLD", 0.10))

        self.order_size = float(getattr(config, "ORDER_SIZE", 100))

    # --- 開くべきか ---
    def should_open_position(self, indicators: dict, position: dict) -> bool:
        rsi   = indicators.get("rsi")
        depth = indicators.get("depth_imbalance") or indicators.get("depth_imb_5")
        taker = indicators.get("taker_bias")

        is_open = bool(position and position.get("is_open"))
        if rsi is None or is_open:
            self.logger.debug(f"[Strategy01] skip open: rsi={rsi}, is_open={is_open}")
            return False

        # --- ロング条件 ---
        long_ok = (
            rsi < self.buy_th and
            depth is not None and depth > +self.depth_thr and
            taker is not None and taker > +self.taker_thr
        )

        # --- ショート条件 ---
        short_ok = (
            rsi > self.sell_th and
            depth is not None and depth < -self.depth_thr and
            taker is not None and taker < -self.taker_thr
        )

        self.logger.debug(
            f"[Strategy01.should_open] rsi={rsi}, depth={depth}, taker={taker}, "
            f"long_ok={long_ok}, short_ok={short_ok}"
        )

        return long_ok or short_ok

    # --- シグナル生成（向きと枚数） ---
    def generate_signal(self, indicators: dict, position: dict) -> dict:
        rsi        = indicators.get("rsi")
        depth      = indicators.get("depth_imbalance") or indicators.get("depth_imb_5")
        taker      = indicators.get("taker_bias")
        spread_bps = indicators.get("spread_bps")
        mom_1      = indicators.get("mom_1s")
        mom_5      = indicators.get("mom_5s")
        vol        = indicators.get("volatility")
        slope      = indicators.get("trend_slope")
        liq        = indicators.get("liq_ratio")

        side = "None"
        if rsi is not None:
            if (
                rsi < self.buy_th
                and depth is not None and depth > +self.depth_thr
                and taker is not None and taker > +self.taker_thr
            ):
                side = "Buy"
            elif (
                rsi > self.sell_th
                and depth is not None and depth < -self.depth_thr
                and taker is not None and taker < -self.taker_thr
            ):
                side = "Sell"

        # noteを拡張
        note = (
            f"rsi={rsi if rsi is not None else 'NA'}, "
            f"depth={depth}, taker={taker}, "
            f"spread_bps={spread_bps}, mom1={mom_1}, mom5={mom_5}, "
            f"vol={vol}, slope={slope}, liq={liq}"
        )

        self.logger.debug(f"[Strategy01.generate_signal] side={side}, note={note}")

        return {
            "side": side,
            "qty": self.order_size,
            "maker": False,
            "note": note,
        }

    # --- 閉じるべきか ---
    def should_close_position(self, indicators: dict, position: dict) -> bool:
        rsi = indicators.get("rsi")
        if rsi is None or not position or not position.get("is_open"):
            self.logger.debug(f"[Strategy01.should_close] skip close: rsi={rsi}, position={position}")
            return False

        side = position.get("side")
        if side == "Buy":
            close_ok = rsi >= self.exit_long
        elif side == "Sell":
            close_ok = rsi <= self.exit_short
        else:
            close_ok = False

        self.logger.debug(f"[Strategy01.should_close] side={side}, rsi={rsi}, close_ok={close_ok}")
        return close_ok

# FIXME: RSI/BB に基づくクローズ条件（Strategy02）導入予定
# FIXME: features.py (WS特徴量) の depth/taker/spread を活用するロジック未実装
