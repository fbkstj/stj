"""L5 長照監護的判斷規則（不碰影像，只看「人的外框」隨時間的變化，方便測試）。

姿勢：外框「寬÷高」大於 1.3 → 橫躺；小於 0.9 → 直立；中間 → 彎腰或坐下。
跌倒：之前是直立，之後橫躺「持續 fall_sec 秒」→ 緊急。彎腰、坐下不會變成橫躺，所以不會誤報。
久未活動：畫面中有人，但中心點移動沒超過 move_px 像素，持續 inactive_min 分鐘 → 注意。
"""
from __future__ import annotations

LYING_RATIO = 1.3
UPRIGHT_RATIO = 0.9
UPRIGHT_MEMORY_SEC = 10     # 橫躺前 10 秒內要曾經直立，才算「跌倒」


def posture(box) -> str:
    if box is None:
        return "none"
    x, y, w, h = box
    r = w / max(h, 1)
    if r > LYING_RATIO:
        return "lying"
    if r < UPRIGHT_RATIO:
        return "upright"
    return "bent"


class CareMonitor:
    def __init__(self, fall_sec=3.0, inactive_min=60.0, move_px=25.0, activity_every_min=5.0):
        self.fall_sec = fall_sec
        self.inactive_sec = inactive_min * 60
        self.move_px = move_px
        self.activity_sec = activity_every_min * 60
        self.reset()

    def reset(self):
        self.last_upright = None     # 最近一次直立的時間
        self.lying_since = None
        self.fallen = False          # 已經發過跌倒通報，等站起來才重設
        self.anchor = None           # 用來判斷有沒有移動的基準點
        self.still_since = None
        self.inactive_sent = False
        self.last_activity = None
        self.state = "none"

    def update(self, t: float, box) -> list[tuple[str, str, str]]:
        """t：第幾秒；box：人的外框 (x, y, w, h) 或 None。回傳要發的事件 [(kind, level, message)]。"""
        out = []
        self.state = posture(box)
        if self.state == "none":
            self.lying_since = None
            self.anchor = None
            self.still_since = None
            return out
        x, y, w, h = box
        center = (x + w / 2, y + h / 2)

        # ---- 跌倒 ----
        if self.state == "upright":
            self.last_upright = t
            self.lying_since = None
            self.fallen = False
        elif self.state == "lying":
            if self.lying_since is None:
                self.lying_since = t
            recently_upright = self.last_upright is not None and self.lying_since - self.last_upright <= UPRIGHT_MEMORY_SEC
            if not self.fallen and recently_upright and t - self.lying_since >= self.fall_sec:
                self.fallen = True
                out.append(("fall", "urgent", f"疑似跌倒：倒地已超過 {self.fall_sec:g} 秒，請立即確認"))
        else:
            self.lying_since = None

        # ---- 移動與久未活動 ----
        moved = self.anchor is None or abs(center[0] - self.anchor[0]) + abs(center[1] - self.anchor[1]) > self.move_px
        if moved:
            self.anchor = center
            self.still_since = t
            self.inactive_sent = False
            if self.last_activity is None or t - self.last_activity >= self.activity_sec:
                self.last_activity = t
                out.append(("activity", "info", "偵測到活動"))
        elif (not self.inactive_sent and not self.fallen and self.still_since is not None
              and t - self.still_since >= self.inactive_sec):
            self.inactive_sent = True
            span = f"{self.inactive_sec / 60:g} 分鐘" if self.inactive_sec >= 60 else f"{self.inactive_sec:g} 秒"
            out.append(("inactive", "warn", f"長時間沒有活動：已超過 {span}幾乎沒有移動，請關心一下"))
        return out
