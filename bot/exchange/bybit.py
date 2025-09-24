# bot/exchange/bybit.py
from __future__ import annotations
import time
from typing import Dict, List, Any, Optional


class BybitExchange:
    """
    本番化の際は pybit 等の HTTP/WS クライアントを注入するだけでOKな形を維持。
    インターフェイス:
      - get_last_price()       -> float
      - get_orderbook()        -> {"best_bid": float, "best_ask": float}
                                  または {"bids":[[price,qty],...], "asks":[[price,qty],...]}
      - get_current_position() -> {"is_open": bool, "side": "Buy"/"Sell"/None,
                                   "size": float, "entry_price": float}
      - place_market_order(side, qty) -> 取引所レスポンス (dict)
      - fetch_ohlcv(timeframe, limit) -> List[Dict[str, Any]]  # 互換のため残置（ダミー）
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.symbol: str = getattr(config, "SYMBOL", "DOGEUSDT")

        # ダミー内部価格（本番はAPIで更新）
        self._last_price: float = 0.1

        # 実運用用のキー（保持だけ。使うのは本番実装時）
        self.api_key: str = getattr(config, "BYBIT_API_KEY", "")
        self.api_secret: str = getattr(config, "BYBIT_API_SECRET", "")

        # TODO: 本番化の際に pybit の HTTP/WS クライアントを初期化
        # from pybit.unified_trading import HTTP
        # self.http = HTTP(api_key=self.api_key, api_secret=self.api_secret, testnet=False)

    # ---- 市場データ（ダミー / フォールバック） ----
    def get_last_price(self) -> float:
        """
        本番: v5/market/tickers 等から該当シンボルの lastPrice を取得して返す。
        ここではダミー値を返す。
        """
        return float(self._last_price)

    def get_orderbook(self) -> Dict[str, float]:
        """
        本番: v5/market/orderbook から best bid/ask を構築して返す。
        ここでは last を中心に適当なスプレッドでダミー返却。
        """
        mid = self.get_last_price() or 0.1
        spread = max(mid * 0.0005, 0.0001)
        return {"best_bid": mid - spread / 2, "best_ask": mid + spread / 2}

    def get_current_position(self) -> Dict[str, Any]:
        """
        本番: v5/position/list で self.symbol を抽出し、以下の形に正規化して返す:
          { "is_open": bool, "side": "Buy"/"Sell"/None, "size": float, "entry_price": float }
        ここでは未保有ダミー。
        """
        return {"is_open": False, "side": None, "size": 0.0, "entry_price": 0.0}

    # ---- 取引（ダミー） ----
    def place_market_order(self, side: str, qty: float) -> Dict[str, Any]:
        """
        本番: v5/order/create にて MARKET 注文を実行。
        ここではログ出力と内部ダミー価格の微調整のみ行う。
        """
        self.logger.info(f"[EXCHANGE] MARKET {side} {qty} {self.symbol}")
        # ダミーで価格をわずかに動かす（約定で中立っぽく推移）
        factor = 0.0002 if side.lower() == "buy" else -0.0002
        self._last_price = (self._last_price or 0.1) * (1.0 + factor)
        return {"status": "ok", "side": side, "qty": qty, "symbol": self.symbol}

    # ---- 互換：core/indicators 用のダミーOHLCV ----
    def fetch_ohlcv(self, timeframe: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        互換のため残置。インジ側が close/high/low/volume を読む前提のため、
        ダミーで単調増加するクローズ配列を返す。
        本番は v5/market/kline などに差し替え。
        """
        base = self._last_price or 0.1
        out: List[Dict[str, Any]] = []
        for i in range(limit):
            close = base + i * 0.0005
            out.append({
                "close": close,
                "high": close * 1.002,
                "low": close * 0.998,
                "volume": 10.0,
            })
        return out
