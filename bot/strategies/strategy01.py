# bot/strategies/strategy01.py
from __future__ import annotations
import logging
from typing import Dict, Any

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
        self.buy_th  = float(getattr(config, "RSI_BUY", 35))
        self.sell_th = float(getattr(config, "RSI_SELL", 65))
        self.exit_long  = float(getattr(config, "RSI_EXIT_LONG", 55))
        self.exit_short = float(getattr(config, "RSI_EXIT_SHORT", 45))

        # --- 板厚/成行偏りしきい値（Stage4追加） ---
        self.depth_thr = float(getattr(config, "DEPTH_IMB_THRESHOLD", 0.15))
        self.taker_thr = float(getattr(config, "TAKER_BIAS_THRESHOLD", 0.10))

        self.order_size = float(getattr(config, "ORDER_SIZE", 100))

    # ========== 開く/閉じる判定 ==========

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

        return bool(long_ok or short_ok)

    def should_close_position(self, indicators: dict, position: dict) -> bool:
        if not position or not position.get("is_open"):
            return False

        side = position.get("side")
        rsi  = indicators.get("rsi")
        if rsi is None:
            return False

        # ロング→RSIがEXIT_LONGを超えたら利確/撤退
        if side == "Buy" and rsi >= self.exit_long:
            return True
        # ショート→RSIがEXIT_SHORTを下回ったら利確/撤退
        if side == "Sell" and rsi <= self.exit_short:
            return True

        return False

    # ========== シグナル生成 ==========

    def generate_signal(self, indicators: dict, position: dict) -> Dict[str, Any]:
        """
        方向と枚数を返す。ロング/ショートのどちらか一方。
        """
        if position and position.get("is_open"):
            return {}

        rsi        = indicators.get("rsi")
        depth      = indicators.get("depth_imbalance") or indicators.get("depth_imb_5")
        taker      = indicators.get("taker_bias")
        spread_bps = indicators.get("spread_bps")
        mom_1      = indicators.get("mom_1s")
        mom_5      = indicators.get("mom_5s")

        if rsi is None or depth is None or taker is None:
            return {}

        if rsi < self.buy_th and depth > +self.depth_thr and taker > +self.taker_thr:
            return {"side": "Buy",  "qty": self.order_size, "meta": {"spr_bps": spread_bps, "m1": mom_1, "m5": mom_5}}
        if rsi > self.sell_th and depth < -self.depth_thr and taker < -self.taker_thr:
            return {"side": "Sell", "qty": self.order_size, "meta": {"spr_bps": spread_bps, "m1": mom_1, "m5": mom_5}}

        return {}
