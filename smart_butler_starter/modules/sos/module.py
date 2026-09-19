"""L12 一鍵／語音求救：按鍵、管理介面按鈕、或對管家說出關鍵字，立刻發出緊急通報並附截圖。

- 10 秒內（sos.cooldown_sec）重複觸發只算一次，避免連按洗版
- 記錄從觸發到送出花了多少毫秒，目標 3 秒（3000 毫秒）內
"""
from __future__ import annotations

import time

from core.module import Module


class SosModule(Module):
    name = "sos"
    title = "一鍵求救"
    interval = 1.0
    listens = {"sos_request": "on_request"}     # 對話中說出「救命」等關鍵字

    def setup(self):
        self.last_trigger = None
        self.last_latency_ms = None

    def on_request(self, event):
        self.trigger(event.data.get("trigger", "語音"))

    def trigger(self, source: str = "鍵盤") -> bool:
        """回傳 True 代表送出；False 代表在冷卻時間內，被當成重複觸發。"""
        now = self.clock.monotonic()
        if self.last_trigger is not None and now - self.last_trigger < self.cfg["cooldown_sec"]:
            self.log.info("%g 秒內重複觸發，只算一次", self.cfg["cooldown_sec"])
            return False
        self.last_trigger = now
        t0 = time.perf_counter()
        snap = None
        if not self.app.privacy:
            for name in ("care", "camera"):
                cam = self.app.modules.get(name)
                if cam is not None and getattr(cam, "latest_frame", None) is not None:
                    snap = cam.snapshot("sos")
                    break
        self.publish("sos", "urgent", f"長輩按下求救（{source}），請立即聯絡！", snap, trigger=source)
        self.last_latency_ms = round((time.perf_counter() - t0) * 1000)
        self.log.info("求救通報已送出，從觸發到送出 %d 毫秒", self.last_latency_ms)
        return True
