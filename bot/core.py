# bot/core.py
import time
from bot.exchange.bybit import BybitExchange
from bot.strategies.strategy01 import Strategy01
from bot.utils.order_executor import OrderExecutor
from bot.utils.position_handler import PositionHandler
from bot.features.indicators import load_indicators_from_env
# from bot.features.features import compute_market_features  
# ↑ 必要に応じて併用可能（現在はindicatorsに統合済み）

class BotRunner:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        self.exchange = BybitExchange(config, logger)
        self.strategy = Strategy01(config, logger)
        self.order_executor = OrderExecutor(self.exchange, config, logger)
        self.position_handler = PositionHandler(self.exchange, config, logger)

        # インジケータ・パイプライン（features統合済み）
        self.indicators = load_indicators_from_env(config)

        # ★ 起動時の一度だけ、実ポジから内部状態へ同期
        try:
            boot_position = self.exchange.get_current_position()
        except Exception:
            boot_position = {"is_open": False, "side": None, "size": 0.0, "entry_price": 0.0}

        # 再起動時の取り違え防止。flatでも“初回のみ”は反映させたいので force_flat=True
        self.position_handler.sync_from_exchange(boot_position, force_flat=True)

    def run(self):
        # 価格データの取得と特徴量計算
        price_data = self.exchange.fetch_ohlcv("1m", limit=100)
        indicators = self.indicators(price_data, exchange=self.exchange)

        # 現在の実ポジ（戦略ロジック用に参照）
        position = self.exchange.get_current_position()

        # 先に開閉の判定を済ませてから、エッジ検出で一度だけ実行
        open_ok  = self.strategy.should_open_position(indicators, position)
        close_ok = self.strategy.should_close_position(indicators, position)

        if open_ok:
            signal = self.strategy.generate_signal(indicators, position)
            side = signal.get("side")
            if side in ("Buy", "Sell") and self.position_handler.entry_edge(True, side):
                self.order_executor.execute(signal)
                self.position_handler.mark_entered(side)

        elif close_ok and self.position_handler.close_edge(True):
            self.order_executor.close_position(position, reason="strategy")
            self.position_handler.mark_closed()

        # ポーリング間隔
        time.sleep(int(getattr(self.config, "POLL_SEC", 15)))

# FIXME: Strategy02 / Strategy03 実装後に呼び出し追加
# FIXME: CircuitBreakerV2 (Stage3) は拡張済みだが、WS特徴量との連携未実装
# FIXME: LinUCBセレクタ導入後 (Stage5) に strategy 選択処理を差し替える必要あり
