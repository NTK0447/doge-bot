# test_runner.py
from bot.strategies.strategy01 import Strategy01
from bot.utils.order_executor import OrderExecutor
from bot.utils.position_handler import PositionHandler
from bot.features.indicators import compute_indicators
from bot.exchange.bybit import BybitExchange

# モック環境やダミーデータを使って簡単に呼び出す
def main():
    print("✅ test_runner 起動")

    exchange = BybitExchange()
    strategy = Strategy01(exchange)
    position_handler = PositionHandler(exchange)
    order_executor = OrderExecutor(exchange)

    # テスト用ダミーデータ（空のkline等）
    dummy_klines = []
    dummy_orderbook = {}
    dummy_tape = []

    try:
        result = strategy.should_open_position(dummy_klines, dummy_orderbook, dummy_tape)
        print(f"🚦 should_open_position 結果: {result}")
    except Exception as e:
        print(f"❌ エラー発生: {e}")

if __name__ == "__main__":
    main()
