"""
模擬情境：一段 3 分鐘的「穿堂演練」，由程式安排每個人的位置與動作。

make_demo_detections.py 用它產生練習用的偵測紀錄（模擬 YOLO 的輸出，含漏抓與誤判），
make_scenario_video.py 用它畫出動作要求示意影片。兩者看到的是同一套情境。

畫面 1280×720，人物的高度依照離鏡頭遠近（腳的位置）變化。
"""
import math
import random

from threat_rules import Detection

W, H = 1280, 720
FPS = 10                      # 偵測紀錄每秒幾筆（每 0.1 秒辨識一次）
DURATION = 180.0
DESK_BOX = (985, 500, 1025, 528)   # 桌上剪刀的位置

# 正確答案（和 videos/demo_truth.csv 相同）
TRUTH = [
    ("持械", 12.0, 20.0, "A 同學拿起剪刀"),
    ("倒地", 52.0, 60.0, "D 同學在軟墊上倒地"),
    ("奔逃", 83.0, 88.0, "兩組各 3 人跑過穿堂"),
    ("聚集", 112.0, 125.0, "16 人聚在一起"),
    ("持械", 133.0, 137.0, "F 同學拿刀（演練用道具）"),
    ("持械", 152.0, 158.0, "G 同學拿剪刀，但距離遠、角度差"),
]

# 情境說明（示意影片的字幕也用這份）
SCENES = [
    (0, 10, "情境 0：平常的穿堂，只有人走動"),
    (10, 26, "情境 1：有人拿起剪刀並持續拿著"),
    (26, 40, "情境 2：剪刀放在桌上，有人從桌旁走過"),
    (40, 50, "情境 3：剪刀只在鏡頭前晃一下，還有零星誤判"),
    (50, 65, "情境 4：有人倒地超過 3 秒"),
    (65, 80, "情境 5：有人蹲下綁鞋帶 1.5 秒"),
    (80, 95, "情境 6：人群快速跑過"),
    (95, 110, "情境 7：三個人快步走過"),
    (110, 130, "情境 8：人群聚集"),
    (130, 150, "情境 9：有人持刀"),
    (150, 165, "情境 10：剪刀離鏡頭遠，信心度偏低"),
    (165, 180, "情境 11：手機被誤認成刀子"),
]


def height_at(foot):
    """越靠近鏡頭（腳的 y 越大）人越高。"""
    return 0.55 * foot - 90


def person_box(x, foot, pose):
    h = height_at(foot)
    if pose == "lie":
        w, hh = h * 1.0, h * 0.35
    elif pose == "bend":
        w, hh = h * 0.85, h * 0.55
    else:
        w, hh = h * 0.4, h
    return (x - w / 2, foot - hh, x + w / 2, foot)


def hand_box(pbox, size=30):
    x1, y1, x2, y2 = pbox
    hx = x2 - 4
    hy = y1 + (y2 - y1) * 0.45
    return (hx, hy - size / 2, hx + size, hy + size / 2)


def _walk(t, t0, t1, x0, x1):
    if t < t0 or t > t1:
        return None
    return x0 + (x1 - x0) * (t - t0) / (t1 - t0)


def actors_at(t):
    """回傳這個時間點畫面裡的人：[{id, x, foot, pose, hold, run}]
    hold：拿著的東西 (類別, 信心度) 或 None；run：是否在跑（畫圖用）"""
    people = []
    # 背景：一直在慢慢走的 P0（來回走）
    span = 980
    pos = (t * 50) % (2 * span)
    x = 150 + (pos if pos < span else 2 * span - pos)
    people.append({"id": "P0", "x": x, "foot": 470, "pose": "stand", "hold": None, "run": False})

    if 8 <= t < 26:                                   # 情境 1
        hold = (76, 0.55) if 12.0 <= t < 20.0 else None
        people.append({"id": "A", "x": 400, "foot": 600, "pose": "stand", "hold": hold, "run": False})
    x = _walk(t, 31.0, 36.1, 700, 1300)               # 情境 2：從桌旁走過
    if x is not None:
        people.append({"id": "B", "x": x, "foot": 600, "pose": "stand", "hold": None, "run": False})
    if 40 <= t < 50:                                  # 情境 3
        hold = (76, 0.6) if 42.0 <= t < 42.4 else None
        people.append({"id": "C", "x": 600, "foot": 620, "pose": "stand", "hold": hold, "run": False})
    if 50 <= t < 65:                                  # 情境 4
        pose = "lie" if 52.0 <= t < 60.0 else "stand"
        people.append({"id": "D", "x": 800, "foot": 640, "pose": pose, "hold": None, "run": False})
    if 65 <= t < 80:                                  # 情境 5
        pose = "bend" if 68.0 <= t < 69.5 else "stand"
        people.append({"id": "E", "x": 500, "foot": 600, "pose": pose, "hold": None, "run": False})
    for i, (t0, foot, direction) in enumerate([(83.0, 520, 1), (83.2, 580, 1), (83.4, 650, 1),
                                               (85.4, 540, -1), (85.6, 600, -1), (85.8, 670, -1)]):
        x0, x1 = (-60, 1340) if direction > 0 else (1340, -60)
        x = _walk(t, t0, t0 + 1400 / 750, x0, x1)     # 情境 6：每秒 750 像素
        if x is not None:
            people.append({"id": f"R{i}", "x": x, "foot": foot, "pose": "stand", "hold": None, "run": True})
    for i, (t0, foot) in enumerate([(97.0, 540), (97.3, 600), (97.6, 660)]):
        x = _walk(t, t0, t0 + 1400 / 250, -60, 1340)  # 情境 7：每秒 250 像素
        if x is not None:
            people.append({"id": f"K{i}", "x": x, "foot": foot, "pose": "stand", "hold": None, "run": False})
    if 112.0 <= t < 125.0:                            # 情境 8：16 人
        for i in range(16):
            r, c = divmod(i, 8)
            people.append({"id": f"G{i}", "x": 260 + c * 110 + r * 40, "foot": 560 + r * 70,
                           "pose": "stand", "hold": None, "run": False})
    if 130 <= t < 150:                                # 情境 9
        hold = (43, 0.5) if 133.0 <= t < 137.0 else None
        people.append({"id": "F", "x": 900, "foot": 600, "pose": "stand", "hold": hold, "run": False})
    if 150 <= t < 165:                                # 情境 10
        hold = (76, 0.27) if 152.0 <= t < 158.0 else None
        people.append({"id": "G", "x": 350, "foot": 500, "pose": "stand", "hold": hold, "run": False})
    if 165 <= t < 180:                                # 情境 11：手機
        hold = (43, 0.28) if 168.0 <= t < 170.5 else None
        people.append({"id": "H", "x": 700, "foot": 620, "pose": "stand", "hold": hold, "run": False,
                       "phone": True})
    return people


DESK_SCISSORS = (26.0, 38.0)
BLIPS = [45.3, 47.1, 77.2, 101.5, 144.4]      # 只出現一格的誤判


def detections_at(t, rng):
    """模擬 YOLO 在時間 t 的輸出（含框的抖動、漏抓）。"""
    dets = []

    def jitter(box, px):
        return tuple(v + rng.uniform(-px, px) for v in box)

    def clip(box):
        x1, y1, x2, y2 = box
        return (max(0, x1), max(0, y1), min(W, x2), min(H, y2))

    for a in actors_at(t):
        if not 0 <= a["x"] <= W:
            continue
        pbox = person_box(a["x"], a["foot"], a["pose"])
        if rng.random() > 0.03:
            dets.append(Detection(0, round(rng.uniform(0.6, 0.92), 2), clip(jitter(pbox, 3))))
        if a["hold"] and rng.random() > 0.12:
            cls, conf = a["hold"]
            c = min(0.95, max(0.05, conf + rng.uniform(-0.03, 0.03)))
            dets.append(Detection(cls, round(c, 2), jitter(hand_box(pbox), 2)))
        if round(t, 1) in BLIPS and a["id"] == "P0":
            dets.append(Detection(76, 0.4, hand_box(pbox)))
    if DESK_SCISSORS[0] <= t < DESK_SCISSORS[1] and rng.random() > 0.1:
        dets.append(Detection(76, round(rng.uniform(0.45, 0.6), 2), jitter(DESK_BOX, 1.5)))
    return dets


def build_frames(seed=7):
    rng = random.Random(seed)
    frames = []
    n = int(DURATION * FPS)
    for i in range(n + 1):
        t = round(i / FPS, 3)
        frames.append((t, H, W, detections_at(t, rng)))
    return frames


def scene_title(t):
    for t0, t1, text in SCENES:
        if t0 <= t < t1:
            return text
    return ""


def speed_fh(px_per_sec):
    return px_per_sec / H


assert math.isclose(speed_fh(720), 1.0)
