"""把關卡3的判斷整理成可重複使用的模組,給關卡4、5 匯入。"""
import cv2

PERSON = 0
WEAPONS = {43: "刀子", 34: "球棒", 76: "剪刀"}
CONF = 0.3


def expand(box, ratio):
    x1, y1, x2, y2 = box
    dw, dh = (x2 - x1) * ratio, (y2 - y1) * ratio
    return x1 - dw, y1 - dh, x2 + dw, y2 + dh


def overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def find_held_weapons(model, frame):
    """回傳 (手持的危險物品清單, 人數),並直接在 frame 上畫框。"""
    result = model.predict(frame, classes=[PERSON, *WEAPONS], conf=CONF,
                           imgsz=416, verbose=False)[0]
    people, weapons = [], []
    for box in result.boxes:
        cls = int(box.cls[0])
        xyxy = tuple(box.xyxy[0].tolist())
        (people if cls == PERSON else weapons).append((cls, xyxy))

    held = []
    for cls, w in weapons:
        if any(overlap(w, expand(p, 0.15)) for _, p in people):
            held.append(WEAPONS[cls])
            x1, y1, x2, y2 = map(int, w)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
    for _, p in people:
        x1, y1, x2, y2 = map(int, p)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
    return held, len(people)


class SustainedFlag:
    """訊號要「持續」sustain_sec 秒才算成立;短暫消失 grace_sec 秒內不歸零。"""

    def __init__(self, sustain_sec, grace_sec=0.8):
        self.sustain_sec = sustain_sec
        self.grace_sec = grace_sec
        self.since = None
        self.last_true = None

    def update(self, now_true, now):
        if now_true:
            if self.since is None:
                self.since = now
            self.last_true = now
        elif self.last_true is not None and now - self.last_true > self.grace_sec:
            self.since = self.last_true = None
        return self.progress(now) >= 1

    def progress(self, now):
        """0~1,拿來畫進度條。
        用「最後一次真的看到」計算:物品短暫消失時進度條停住,不會自己跑滿。"""
        if self.since is None:
            return 0.0
        return min(1.0, (self.last_true - self.since) / self.sustain_sec)
