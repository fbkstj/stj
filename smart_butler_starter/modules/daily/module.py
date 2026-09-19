"""L11 每日平安回報模組：每天 daily.time 送出一次摘要。"""
from __future__ import annotations

from core.clock import parse_hhmm
from core.module import Module
from modules.daily.summary import collect, format_summary


class DailyModule(Module):
    name = "daily"
    title = "每日平安回報"
    interval = 5.0

    def setup(self):
        # 啟動時如果已經過了今天的回報時間，今天就不補送（避免一開機就收到一則回報）
        now = self.clock.now()
        h, m = parse_hhmm(self.cfg["time"])
        self.sent_day = now.date() if (now.hour, now.minute) >= (h, m) else None

    def step(self):
        now = self.clock.now()
        h, m = parse_hhmm(self.cfg["time"])
        if self.sent_day != now.date() and (now.hour, now.minute) >= (h, m):
            self.sent_day = now.date()
            self.send_summary(now.date(), now)

    def send_summary(self, day, until=None) -> str:
        s = collect(self.app.store, day, until, self.settings["routine"]["activity_kinds"])
        text = format_summary(s, self.settings["system"]["name"])
        self.publish("daily_summary", "info", text, **{k: v for k, v in s.items()
                                                      if isinstance(v, (int, str)) and not isinstance(v, bool)})
        return text
