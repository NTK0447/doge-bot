# bot/utils/position_handler.py
class PositionHandler:
    """
    DRY_RUN/実運用を問わず、“内部状態”でポジション遷移を管理。
      - 未保有 -> 保有 になった瞬間だけエントリーを許可
      - 保有   -> 未保有 になった瞬間だけクローズを許可
    Exchange側の実ポジは参照（get_current_position）はするが、
    ここでは “重複実行の抑止” を責務にする。
    """
    def __init__(self, exchange=None, config=None, logger=None):
        self.exchange = exchange
        self.config = config
        self.logger = logger
        self._in_position = False
        self._side = None  # "Buy" or "Sell"

    # ---- 起動時のみ：実ポジ→内部状態 同期 ----
    def sync_from_exchange(self, exchange_position: dict | None, force_flat: bool = False):
        """
        起動直後などに一度だけ呼び出して、内部状態を実ポジに合わせる。
        force_flat=True の場合、実ポジがフラットなら内部状態も必ずフラットに初期化する。
        """
        prev_in, prev_side = self._in_position, self._side

        is_open = bool(exchange_position and exchange_position.get("is_open"))
        side = exchange_position.get("side") if exchange_position else None

        if force_flat and not is_open:
            # 実ポジがフラット→内部もフラットに
            self._in_position, self._side = False, None
            msg = "flat"
        else:
            # 実ポジが開いているなら内部も合わせる
            self._in_position = bool(is_open)
            self._side = side if is_open else None
            msg = f"in_position={self._in_position}, side={self._side}"

        if self.logger:
            self.logger.info(
                f"[PositionHandler] synced from exchange: {msg} "
                f"(was in_position={prev_in}, side={prev_side})"
            )

    # ---- 遷移判定 ----
    def entry_edge(self, want_open: bool, side: str) -> bool:
        """
        want_open: strategy から「今はエントリーすべき」判定
        side:     "Buy" or "Sell"
        """
        if want_open and not self._in_position:
            if self.logger:
                self.logger.info(f"[PositionHandler] entry_edge detected (side={side})")
            return True
        return False

    def close_edge(self, want_close: bool) -> bool:
        if want_close and self._in_position:
            if self.logger:
                self.logger.info("[PositionHandler] close_edge detected")
            return True
        return False

    # ---- 状態更新 ----
    def mark_entered(self, side: str):
        self._in_position = True
        self._side = side
        if self.logger:
            self.logger.info(f"[PositionHandler] marked entered: in_position=True, side={side}")

    def mark_closed(self):
        self._in_position = False
        self._side = None
        if self.logger:
            self.logger.info("[PositionHandler] marked closed: in_position=False")

    # （必要なら）外部参照
    @property
    def in_position(self) -> bool:
        return self._in_position

    @property
    def side(self) -> str | None:
        return self._side
