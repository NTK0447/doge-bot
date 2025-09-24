# bot/features/features.py
import time
import numpy as np
from collections import deque
from typing import Any, Dict
from datetime import datetime

# --- 内部状態を保持するシンプルなクラス ---
class FeatureState:
    def __init__(self, maxlen: int = 500):
        self.prices = deque(maxlen=maxlen)
        self.times = deque(maxlen=maxlen)

feature_state = FeatureState()


def _extract_best(ob: dict) -> tuple[float, float] | None:
    bids = ob.get("bids")
    asks = ob.get("asks")
    if not bids or not asks:
        return None
    try:
        bb = float(bids[0][0])
        ba = float(asks[0][0])
        return bb, ba
    except Exception:
        return None


def _depth_imbalance(ob: dict, depth: int = 5) -> float | None:
    bids = ob.get("bids")
    asks = ob.get("asks")
    if not bids or not asks:
        return None
    b = sum(float(x[1]) for x in bids[:depth] if x and len(x) >= 2)
    a = sum(float(x[1]) for x in asks[:depth] if x and len(x) >= 2)
    total = a + b
    if total <= 0:
        return 0.0
    return (b - a) / total


def _tick_direction_ratio(prices: deque, lookback: int = 20) -> tuple[float, float]:
    n = min(lookback, len(prices) - 1)
    if n <= 0:
        return 0.0, 0.0
    ups = downs = 0
    for i in range(-1, -n - 1, -1):
        if prices[i] > prices[i - 1]:
            ups += 1
        elif prices[i] < prices[i - 1]:
            downs += 1
    total = ups + downs
    if total == 0:
        return 0.0, 0.0
    return ups / total, downs / total


def _momentum(prices: deque, k: int) -> float:
    if len(prices) <= k:
        return 0.0
    return float(prices[-1] - prices[-1 - k])


def _volatility(prices: deque, short: int = 20, long: int = 60) -> float:
    if len(prices) < long:
        return 0.0
    arr = np.array(prices)
    short_std = np.std(arr[-short:])
    long_std = np.std(arr[-long:])
    if long_std == 0:
        return 0.0
    return short_std / long_std


def _trend_slope(prices: deque, lookback: int = 30) -> float:
    if len(prices) < lookback:
        return 0.0
    y = np.array(prices)[-lookback:]
    x = np.arange(len(y))
    # 線形回帰の傾き
    A = np.vstack([x, np.ones(len(x))]).T
    slope, _ = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(slope)


def _liquidity_ratio(ob: dict, depth: int = 5, full: int = 20) -> float:
    bids = ob.get("bids")
    asks = ob.get("asks")
    if not bids or not asks:
        return 0.0
    b_top = sum(float(x[1]) for x in bids[:depth])
    a_top = sum(float(x[1]) for x in asks[:depth])
    b_full = sum(float(x[1]) for x in bids[:full])
    a_full = sum(float(x[1]) for x in asks[:full])
    total_top = b_top + a_top
    total_full = b_full + a_full
    if total_full <= 0:
        return 0.0
    return total_top / total_full


# --- 公開API -------------------------------------------------------------
def compute_market_features(exchange) -> Dict[str, Any]:
    """
    exchange の get_orderbook()/get_last_price() を使って特徴量を生成。
    core.py から毎ポーリングで呼ばれる想定。
    """
    now = time.time()

    # 価格取得
    try:
        last = float(exchange.get_last_price())
    except Exception:
        last = 0.0

    try:
        ob = exchange.get_orderbook() or {}
    except Exception:
        ob = {}

    bb_ba = _extract_best(ob)
    if bb_ba:
        bb, ba = bb_ba
        mid = (bb + ba) / 2.0
        spread = ba - bb
    else:
        mid = last if last > 0 else 0.0
        spread = mid * 0.0005 if mid > 0 else 0.0

    if last <= 0:
        last = mid

    if last and last > 0:
        feature_state.prices.append(last)
        feature_state.times.append(now)

    # 板厚バランス
    imb5 = _depth_imbalance(ob, depth=5)

    # ティック方向
    up_ratio, down_ratio = _tick_direction_ratio(feature_state.prices, lookback=20)

    # モメンタム
    mom_1 = _momentum(feature_state.prices, k=1)
    mom_5 = _momentum(feature_state.prices, k=5)

    # 追加特徴量
    vol = _volatility(feature_state.prices, short=20, long=60)
    slope = _trend_slope(feature_state.prices, lookback=30)
    liq = _liquidity_ratio(ob, depth=5, full=20)

    # 出力
    out = {
        "mid": mid or 0.0,
        "spread": spread or 0.0,
        "spread_bps": (spread / mid * 1e4) if (mid and mid > 0) else 0.0,
        "depth_imb_5": imb5 if imb5 is not None else 0.0,
        "tick_up_ratio": up_ratio,
        "tick_down_ratio": down_ratio,
        "mom_1s": mom_1,
        "mom_5s": mom_5,
        "volatility": vol,
        "trend_slope": slope,
        "liq_ratio": liq,
    }

    # --- alias を追加（Strategy01 用） ---
    out["depth_imbalance"] = out["depth_imb_5"]
    out["taker_bias"] = out["tick_up_ratio"] - out["tick_down_ratio"]

    return out


# --- WebSocket拡張のダミー関数（Stage4準備） ---
def get_ws_features(snapshot: dict | None = None) -> dict:
    """
    ダミーWS特徴量取得
    snapshot: 板・テープの疑似データ
    return: dict
    """
    # FIXME: 実装予定 - Bybit WSから板・テープデータ取得
    if snapshot is None:
        return {"ws_depth": 0.0, "ws_taker_imbalance": 0.0}
    return {
        "ws_depth": snapshot.get("depth", 0.0),
        "ws_taker_imbalance": snapshot.get("taker_bias", 0.0),
    }

# NOTE: core.py 側で run() ループに組み込む予定
