# bot/core.py
from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from bot.exchange.bybit import BybitExchange
from bot.features.features import MarketFeatures
from bot.features.indicators import IndicatorEngine
from bot.strategies.strategy01 import Strategy01
from bot.utils.order_executor import OrderExecutor
from bot.utils.position_handler import PositionHandler
from bot.utils.trade_logger import TradeLogger

log = logging.getLogger("DogeBot")


@dataclass
class Config:
    # env から読み込むことを想定（main.py等で注入）
    SYMBOL: str = "DOGEUSDT"
    INTERVAL: int = 1  # seconds
    LOG_LEVEL: str = "INFO"
    DRY_RUN: bool = False

    # Stage1〜3 抜粋
    MAX_OPEN_ORDERS: int = 3
    POSITION_COOLDOWN_SEC: int = 30
    ALLOW_PYRAMID: bool = False
    NET_CAP: float = 2000.0

    RETRY_UNFILLED_ORDER: int = 3
    LIMIT_SLIPPAGE_PCT: float = 0.05

    CB_THRESHOLD_PCT: float = 1.5
    CB_LOOKBACK_SEC: int = 10

    # Stage4（features / indicators / strategy01 用）
    RSI_PERIOD: int = 14
    SMA_FAST: int = 9
    SMA_SLOW: int = 21
    BBANDS_PERIOD: int = 20
    BBANDS_STDDEV: float = 2.0
    ATR_PERIOD: int = 14

    # Strategy01 thresholds
    RSI_BUY: float = 35.0
    RSI_SELL: float = 65.0
    RSI_EXIT_LONG: float = 55.0
    RSI_EXIT_SHORT: float = 45.0
    DEPTH_IMB_THRESHOLD: float = 0.15
    TAKER_BIAS_THRESHOLD: float = 0.10
    ORDER_SIZE: float = 100.0

    # logging paths
    LOGS_DIR: str = "logs"


class DogeBotCore:
    """
    Stage4:
      - WS/REST由来の orderbook & trades を features に渡し、スプレッド/板厚/成行偏り/momentum を生成
      - OHLCV からインジケータ（RSI/BB/SMA/ATR等）を生成
      - それらを strategy01 にまとめて渡し、エントリー/クローズ判断
      - 注文は OrderExecutor、仮想残高＆CSVは TradeLogger が担う
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        log.setLevel(getattr(logging, cfg.LOG_LEVEL.upper(), logging.INFO))

        # 取引所I/F
        self.exchange = BybitExchange(symbol=cfg.SYMBOL, dry_run=cfg.DRY_RUN)

        # Feature / Indicator
        self.features = MarketFeatures(symbol=cfg.SYMBOL)
        self.indicator = IndicatorEngine(
            rsi_period=cfg.RSI_PERIOD,
            sma_fast=cfg.SMA_FAST,
            sma_slow=cfg.SMA_SLOW,
            bb_period=cfg.BBANDS_PERIOD,
            bb_std=cfg.BBANDS_STDDEV,
            atr_period=cfg.ATR_PERIOD,
        )

        # Strategy & execution
        self.strategy = Strategy01(cfg, logger=log)
        self.executor = OrderExecutor(self.exchange, logger=log, max_open_orders=cfg.MAX_OPEN_ORDERS)
        self.position = PositionHandler(symbol=cfg.SYMBOL, allow_pyramid=cfg.ALLOW_PYRAMID)

        # Logging（RAW+日次）
        self.tlogger = TradeLogger(symbol=cfg.SYMBOL, logs_dir=cfg.LOGS_DIR, starting_balance=50.0)

        # 内部状態
        self.last_signal: Optional[Dict[str, Any]] = None
        self.cooldown_until: float = 0.0

    # ===== メインループ =====
    def run(self):
        log.info("[Core] Start main loop (Stage4)")
        interval = max(1, int(self.cfg.INTERVAL))
        while True:
            try:
                self.loop_once()
            except Exception as e:
                log.exception(f"[Core] loop error: {e}")
            time.sleep(interval)

    def loop_once(self):
        now = time.time()
        if now < self.cooldown_until:
            return

        # 1) マーケットデータを取得
        orderbook = self.exchange.get_orderbook(depth=50)
        last_trades = self.exchange.get_last_trades(limit=200)
        ohlcv = self.exchange.get_ohlcv(limit=200)  # 1m足想定

        # 2) 特徴量・インジケータ算出
        feat = self.features.compute_market_features(orderbook, last_trades)
        indi = self.indicator.compute_indicators(ohlcv)

        # 3) まとめて strategy に渡す
        indicators = {
            # features
            "spread_bps": feat.get("spread_bps"),
            "depth_imbalance": feat.get("depth_imbalance"),
            "depth_imb_5": feat.get("depth_imb_5"),
            "taker_bias": feat.get("taker_bias"),
            "mom_1s": feat.get("momentum_1s"),
            "mom_5s": feat.get("momentum_5s"),
            "volatility": feat.get("volatility"),
            "trend_slope": feat.get("trend_slope"),
            "liq_ratio": feat.get("liq_ratio"),
            # indicators
            "rsi": indi.get("rsi"),
            "sma_fast": indi.get("sma_fast"),
            "sma_slow": indi.get("sma_slow"),
            "bb_upper": indi.get("bb_upper"),
            "bb_lower": indi.get("bb_lower"),
            "atr": indi.get("atr"),
            "price": indi.get("close"),
        }

        # 4) ポジション状態
        pos = self.position.snapshot()

        # 5) エントリー/クローズ判定
        if self.strategy.should_close_position(indicators, pos):
            self._close_position(indicators, pos)
            return

        if self.strategy.should_open_position(indicators, pos):
            sig = self.strategy.generate_signal(indicators, pos)
            if sig:
                self._open_position(sig, indicators)

    # ===== 実行系 =====
    def _open_position(self, signal: Dict[str, Any], indicators: Dict[str, Any]):
        side = signal.get("side")
        qty = float(signal.get("qty") or 0)
        if not side or qty <= 0:
            return

        price = indicators.get("price")
        note = self._note_from_indicators(indicators, prefix="OPEN")
        self.tlogger.annotate(note)

        ok = self.executor.place_market_order(side=side, qty=qty)
        if ok:
            self.position.on_open(side=side, qty=qty, price=price)
            self.tlogger.log_trade(
                side=side, qty=qty, entry=price, exit=price, fee=0.0,
                note=note
            )
            self.cooldown_until = time.time() + self.cfg.POSITION_COOLDOWN_SEC

    def _close_position(self, indicators: Dict[str, Any], pos: Dict[str, Any]):
        if not pos or not pos.get("is_open"):
            return
        side = "Sell" if pos.get("side") == "Buy" else "Buy"
        qty = float(pos.get("qty") or 0)
        if qty <= 0:
            return

        price = indicators.get("price")
        note = self._note_from_indicators(indicators, prefix="CLOSE")
        self.tlogger.annotate(note)

        ok = self.executor.place_market_order(side=side, qty=qty)
        if ok:
            entry = float(pos.get("entry_price") or price)
            self.position.on_close(exit_price=price)
            self.tlogger.log_trade(
                side=pos.get("side"), qty=qty, entry=entry, exit=price, fee=0.0,
                note=note
            )
            self.cooldown_until = time.time() + self.cfg.POSITION_COOLDOWN_SEC

    # ===== ログ用ノート =====
    def _note_from_indicators(self, ind: Dict[str, Any], prefix: str = "") -> str:
        parts = [
            prefix,
            f"rsi={ind.get('rsi')}",
            f"depth={ind.get('depth_imbalance')}",
            f"taker={ind.get('taker_bias')}",
            f"spr_bps={ind.get('spread_bps')}",
            f"m1={ind.get('mom_1s')}",
            f"m5={ind.get('mom_5s')}",
        ]
        return " | ".join(p for p in parts if p is not None)
