import time
import traceback
import logging
from dotenv import dotenv_values
from bot.core import BotRunner

class Config:
    def __init__(self, values: dict):
        for key, value in values.items():
            if isinstance(value, str):
                if value.lower() == "true":
                    setattr(self, key, True)
                elif value.lower() == "false":
                    setattr(self, key, False)
                else:
                    try:
                        num_val = float(value)
                        setattr(self, key, int(num_val) if num_val.is_integer() else num_val)
                    except ValueError:
                        setattr(self, key, value)
            else:
                setattr(self, key, value)

# === .envの読み込み ===
raw_config = dotenv_values("env/.env")
config = Config(raw_config)

# === ロガー設定 ===
logging.basicConfig(
    level=logging.DEBUG,  # ← INFO → DEBUG に変更
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("DogeBot")

# === BotRunner起動 ===
print("✅ RSI_PERIOD in config:", getattr(config, "RSI_PERIOD", "NOT FOUND"))
runner = BotRunner(config=config, logger=logger)

# === 実行ループ ===
if __name__ == "__main__":
    while True:
        try:
            print("▶ running...")
            runner.run()
        except Exception as e:
            logger.error("❌ Error: %s", e, exc_info=True)
            traceback.print_exc()
        time.sleep(int(getattr(config, "POLL_SEC", 15)))
