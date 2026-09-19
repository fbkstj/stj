"""手勢辨識：把 MediaPipe 的 21 個手部關節點，判斷成手勢名稱，再決定什麼時候觸發動作。

關節點編號（MediaPipe Hands）：
  0 手腕
  1～4   大拇指（4 是指尖）      5～8   食指（5 指根、6 第二關節、8 指尖）
  9～12  中指                    13～16 無名指                 17～20 小指

判斷方法只用「角度」與「長度比例」，所以手轉個角度、離鏡頭遠近不同都能辨識：
  - 手指伸直：指根→第二關節、第二關節→指尖 這兩段幾乎同方向，而且指尖比第二關節離手腕更遠
  - 手掌大小：手腕到中指指根的距離，用來判斷手是不是太遠
"""
import math
from collections import Counter, deque

import numpy as np

GESTURE_NAMES = {
    "open_palm": "手掌張開",
    "point_right": "食指向右",
    "point_left": "食指向左",
    "thumb_up": "大拇指朝上",
    "thumb_down": "大拇指朝下",
    "v_sign": "剪刀手",
    "fist": "握拳",
    "none": "沒有指令",
    "too_far": "手太遠",
    "no_hand": "沒有手",
}
SHORT_NAMES = {"open_palm": "張開", "point_right": "右指", "point_left": "左指", "thumb_up": "讚",
               "thumb_down": "倒讚", "v_sign": "剪刀", "fist": "握拳", "none": "無", "too_far": "太遠"}

FINGERS = {             # (指根, 第二關節, 指尖)
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}


def to_pixels(landmarks, width, height):
    """MediaPipe 的座標是 0～1 的比例，換成像素才不會因畫面長寬比而變形。"""
    return np.array([[p[0] * width, p[1] * height] for p in landmarks], dtype=float)


def _dist(a, b):
    return float(np.hypot(*(a - b)))


def _bend(a, b, c):
    """a→b 與 b→c 兩段的夾角（度）。0 度代表一直線。"""
    v1, v2 = b - a, c - b
    n = np.linalg.norm(v1) * np.linalg.norm(v2)
    if n == 0:
        return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(v1, v2) / n)))))


def direction(v):
    """向量的方向角：0＝右、90＝上、180／-180＝左、-90＝下（畫面的 y 軸朝下，所以要反過來）。"""
    return math.degrees(math.atan2(-v[1], v[0]))


def analyze(pts, image_height, cfg):
    """回傳 (手勢名稱, 細節)。pts 是 21×2 的像素座標。"""
    palm = _dist(pts[0], pts[9])
    info = {"palm": palm}
    if palm < cfg["min_palm_ratio"] * image_height:
        return "too_far", info

    ext = {}
    for name, (mcp, pip, tip) in FINGERS.items():
        straight = _bend(pts[mcp], pts[pip], pts[tip]) < cfg["straight_deg"]
        longer = _dist(pts[0], pts[tip]) > _dist(pts[0], pts[pip]) * 1.1
        ext[name] = straight and longer
    thumb_straight = _bend(pts[2], pts[3], pts[4]) < cfg["thumb_straight_deg"]
    thumb_out = _dist(pts[4], pts[5]) > cfg["thumb_out_ratio"] * palm
    ext["thumb"] = thumb_straight and thumb_out
    info["extended"] = ext

    four = [ext["index"], ext["middle"], ext["ring"], ext["pinky"]]
    n = sum(four)
    tol = cfg["direction_tolerance_deg"]

    if n == 4:
        return "open_palm", info
    if four == [True, True, False, False]:
        spread = abs(direction(pts[8] - pts[5]) - direction(pts[12] - pts[9]))
        spread = min(spread, 360 - spread)
        info["v_spread"] = spread
        return ("v_sign" if spread >= cfg["v_min_spread_deg"] else "none"), info
    if four == [True, False, False, False]:
        ang = direction(pts[8] - pts[5])
        info["angle"] = ang
        if abs(ang) <= tol:
            return "point_right", info
        if abs(ang) >= 180 - tol:
            return "point_left", info
        return "none", info
    if n == 0:
        if ext["thumb"]:
            ang = direction(pts[4] - pts[2])
            info["angle"] = ang
            if abs(ang - 90) <= tol:
                return "thumb_up", info
            if abs(ang + 90) <= tol:
                return "thumb_down", info
            return "none", info
        return "fist", info
    return "none", info


class GestureTrigger:
    """把每一格的手勢，變成「要不要觸發動作」。

    - 平滑：取最近幾格的多數決，一兩格辨識錯不會打斷
    - 蓄力：同一個手勢要維持 hold_sec 秒才觸發（畫面上的進度環）
    - 重複：repeat_sec > 0 的手勢（例如調音量）持續比著會一直觸發
    - 放下再觸發：不重複的手勢觸發一次後，要換手勢才能再觸發
    - 冷卻：任何動作之後 cooldown_sec 秒內，不觸發「別的」動作
    - 手勢鎖：握拳維持 lock_hold_sec 秒切換鎖定；鎖定時只認得握拳
    - 應用程式模式：不同模式有不同的手勢對應，切換模式時用 set_map 換掉
    """

    def __init__(self, cfg, gesture_map=None):
        self.map = gesture_map if gesture_map is not None else cfg["profiles"][cfg["default_profile"]]["gestures"]
        self.cooldown = cfg["cooldown_sec"]
        self.lock_gesture = cfg["lock_gesture"]
        self.lock_hold = cfg["lock_hold_sec"]
        self.history = deque(maxlen=cfg["smooth_frames"])
        self.current = "no_hand"
        self.start = 0.0
        self.fired = False
        self.last_fire = -1e9
        self.last_action = ("", -1e9)
        self.locked = cfg.get("start_locked", False)

    def set_map(self, gesture_map):
        """換成另一個模式的手勢對應；正在蓄力的手勢重新計算，避免切換瞬間誤觸。"""
        self.map = gesture_map
        self.fired = True

    def stable(self, gesture):
        self.history.append(gesture)
        return Counter(self.history).most_common(1)[0][0]

    def update(self, gesture, now):
        """回傳 (穩定後的手勢, 進度 0～1, 事件)。事件是 None 或 dict(action, gesture, held)。"""
        g = self.stable(gesture)
        if g != self.current:
            self.current, self.start, self.fired = g, now, False
        held = now - self.start

        if g == self.lock_gesture:
            if self.fired:
                return g, 1.0, None
            progress = min(1.0, held / self.lock_hold)
            if held >= self.lock_hold:
                self.fired = True
                self.locked = not self.locked
                return g, 1.0, {"action": "lock" if self.locked else "unlock", "gesture": g, "held": held}
            return g, progress, None

        spec = self.map.get(g)
        if not spec or self.locked:
            return g, 0.0, None
        action, hold, repeat = spec["action"], spec["hold_sec"], spec.get("repeat_sec", 0)

        if not self.fired:
            if held < hold:
                return g, held / hold, None
            last_name, last_time = self.last_action
            if action != last_name and now - last_time < self.cooldown:
                return g, 1.0, None
            return g, 1.0, self._fire(action, g, held, now)
        if repeat > 0 and now - self.last_fire >= repeat:
            return g, 1.0, self._fire(action, g, held, now)
        return g, 1.0, None

    def _fire(self, action, g, held, now):
        self.fired = True
        self.last_fire = now
        self.last_action = (action, now)
        return {"action": action, "gesture": g, "held": round(held, 2)}
