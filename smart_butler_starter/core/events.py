"""L2 事件匯流排：模組只負責「發布事件」，存檔、通報、顯示由訂閱者處理。"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

from core.clock import Clock, iso

log = logging.getLogger("events")

LEVELS = ("info", "warn", "urgent")
LEVEL_NAMES = {"info": "資訊", "warn": "注意", "urgent": "緊急"}


@dataclass
class Event:
    source: str                 # 哪個模組發的，例如 care
    kind: str                   # 事件類型，例如 fall、visit、meds_overdue
    level: str                  # info／warn／urgent
    message: str                # 給人看的中文內容
    attachment: str | None = None   # 附件路徑（截圖），可空
    data: dict = field(default_factory=dict)   # 其他資料（給程式用）
    time: str | None = None     # 發布時自動填入台北時間
    id: int | None = None       # 存進資料庫後自動填入

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ValueError(f"事件等級只能是 {LEVELS}，收到 {self.level!r}")


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self, clock: Clock | None = None):
        self.clock = clock or Clock()
        self._subs: list[tuple[Subscriber, set | None]] = []
        self._lock = threading.RLock()
        self.errors: list[str] = []     # 訂閱者出錯的紀錄（最近 50 筆）

    def subscribe(self, callback: Subscriber, kinds=None) -> None:
        """kinds=None 代表訂閱全部事件；也可以只訂閱某幾種，例如 kinds=["fall"]。"""
        with self._lock:
            self._subs.append((callback, set(kinds) if kinds else None))

    def publish(self, event: Event) -> Event:
        if event.time is None:
            event.time = iso(self.clock.now())
        with self._lock:
            subs = list(self._subs)
        for callback, kinds in subs:
            if kinds is not None and event.kind not in kinds:
                continue
            try:
                callback(event)
            except Exception as e:   # 某個訂閱者壞掉，不影響其他訂閱者
                name = getattr(callback, "__qualname__", repr(callback))
                msg = f"{name} 處理事件 {event.kind} 時出錯：{e!r}"
                log.error(msg)
                self.errors = (self.errors + [msg])[-50:]
        return event
