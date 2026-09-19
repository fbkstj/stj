"""L13 作息異常偵測模組：每分鐘檢查一次；同一種異常一天只通報一次。"""
from __future__ import annotations

from core.module import Module
from modules.daily.summary import day_range
from modules.routine.analyzer import check


class RoutineModule(Module):
    name = "routine"
    title = "作息異常偵測"
    interval = 60.0

    def setup(self):
        self.note = "尚未檢查"

    def step(self):
        self.run_check()

    def run_check(self, now=None) -> list[tuple[str, str]]:
        now = now or self.clock.now()
        alerts, self.note = check(self.app.store, now, self.cfg)
        start, end = day_range(now.date())
        done = {e["data"].get("key") for e in self.app.store.query(start, end, kind="routine_alert")}
        new = [(k, msg) for k, msg in alerts if k not in done]
        for key, msg in new:
            self.publish("routine_alert", "warn", msg, key=key)
        return new
