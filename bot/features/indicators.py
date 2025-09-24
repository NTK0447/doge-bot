# bot/features/indicators.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from bot.features.features import compute_market_features

# --- シンプルなインジケータ実装 ---
def calculate_sma(closes: List[float], period: int) -> Optional[float]:
    if not closes or period <= 0 or len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if not closes or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

# --- 環境変数をクロージャで固定 ---
def load_indicators_from_env(config):
    rsi_period = int(getattr(config, "RSI_PERIOD", 14))
    sma_fast   = int(getattr(config, "SMA_FAST", 9))
    sma_slow   = int(getattr(config, "SMA_SLOW", 21))
    bb_window  = int(getattr(config, "BBANDS_PERIOD", getattr(config, "BB_WINDOW", 20)))
    bb_stddev  = float(getattr(config, "BBANDS_STDDEV", getattr(config, "BB_STDDEV", 2)))

    def compute_indicators(price_data: List[Dict[str, Any]], exchange=None) -> Dict[str, Any]:
        closes = [bar["close"] for bar in price_data if "close" in bar]

        # テクニカル指標
        rsi  = calculate_rsi(closes, period=rsi_period)
        smaF = calculate_sma(closes, period=sma_fast)
        smaS = calculate_sma(closes, period=sma_slow)

        out: Dict[str, Any] = {
            "rsi": rsi,
            "sma_fast": smaF,
            "sma_slow": smaS,
            "bb_window": bb_window,
            "bb_stddev": bb_stddev,
            "last_close": closes[-1] if closes else None,
        }

        # --- features.py からのマーケット特徴量を統合 ---
        if exchange:
            try:
                features = compute_market_features(exchange)
                out.update(features)
            except Exception:
                # features計算失敗時は無視して続行
                pass

        return out

    return compute_indicators
