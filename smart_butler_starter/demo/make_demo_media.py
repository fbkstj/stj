"""產生示範資料（固定內容，每次產生都一樣，測試結果才能比較）：

  demo/care_demo.mp4        長照監護：走動 → 彎腰 → 坐下 → 跌倒 → 起身 → 久坐不動（66 秒）
  demo/care_demo_truth.csv  答案：跌倒與久未活動發生在第幾秒
  demo/door_demo.mp4        門口：3 次來訪（第 3 次中間短暫走出畫面，仍算同一次）（60 秒）
  demo/door_demo_truth.csv  答案：每次來訪的開始、結束秒數
  demo/discord_inbox.jsonl  示範模式中「家人在 Discord 留言」的模擬資料

影片是程式畫的火柴人，不會拍到任何真人。執行：python demo/make_demo_media.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
W, H, FPS = 640, 360, 10
FLOOR = 318
PERSON = (70, 55, 45)       # 衣服顏色（BGR）


def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def rot(p, deg):
    r = math.radians(deg)
    x, y = p
    return (x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r))


def skeleton(pose: str, phase: float = 0.0, angle: float = 0.0):
    """回傳以腳底中心為原點的關節座標（y 向下為正）。"""
    if pose == "sit":
        return {"head": (0, -146), "neck": (0, -126), "hip": (0, -62), "knee_l": (34, -62), "knee_r": (34, -60),
                "foot_l": (34, 0), "foot_r": (38, 0), "hand_l": (26, -72), "hand_r": (30, -70), "shoulder": (0, -118)}
    if pose == "bend":
        a = math.radians(70)
        hip = (0, -78)
        neck = (hip[0] + 62 * math.sin(a), hip[1] - 62 * math.cos(a))
        head = (neck[0] + 20 * math.sin(a), neck[1] - 20 * math.cos(a))
        return {"head": head, "neck": neck, "hip": hip, "knee_l": (-4, -40), "knee_r": (4, -40),
                "foot_l": (-8, 0), "foot_r": (8, 0), "hand_l": (neck[0] + 4, -22), "hand_r": (neck[0] - 4, -20),
                "shoulder": neck}
    s = 14 * math.sin(phase) if pose == "walk" else 0.0
    pts = {"head": (0, -160), "neck": (0, -140), "hip": (0, -78), "knee_l": (-s / 2, -40), "knee_r": (s / 2, -40),
           "foot_l": (-s, 0), "foot_r": (s, 0), "hand_l": (-10 + s * 0.6, -86), "hand_r": (10 - s * 0.6, -86),
           "shoulder": (0, -132)}
    if angle:
        pts = {k: rot(v, angle) for k, v in pts.items()}
        lift = 10 * math.sin(math.radians(angle))
        pts = {k: (x, y - lift) for k, (x, y) in pts.items()}
    return pts


def draw_person(img, fx, pose, phase=0.0, angle=0.0, color=PERSON, floor=FLOOR):
    p = {k: (int(fx + x), int(floor + y)) for k, (x, y) in skeleton(pose, phase, angle).items()}
    for a, b in (("neck", "hip"), ("hip", "knee_l"), ("knee_l", "foot_l"), ("hip", "knee_r"),
                 ("knee_r", "foot_r"), ("shoulder", "hand_l"), ("shoulder", "hand_r")):
        cv2.line(img, p[a], p[b], color, 13, cv2.LINE_AA)
    cv2.circle(img, p["head"], 17, color, -1, cv2.LINE_AA)


# ---------- 長照監護影片 ----------
CHAIR_X = 470


def care_background():
    img = np.full((H, W, 3), (205, 212, 218), np.uint8)
    img[FLOOR - 2:] = (150, 160, 168)
    cv2.rectangle(img, (40, 60), (170, 170), (180, 200, 215), -1)          # 窗戶
    cv2.rectangle(img, (40, 60), (170, 170), (120, 130, 140), 3)
    cv2.rectangle(img, (CHAIR_X - 30, FLOOR - 68), (CHAIR_X + 50, FLOOR - 56), (60, 110, 150), -1)   # 椅面
    cv2.rectangle(img, (CHAIR_X - 30, FLOOR - 150), (CHAIR_X - 18, FLOOR - 56), (60, 110, 150), -1)  # 椅背
    for x in (CHAIR_X - 28, CHAIR_X + 42):
        cv2.line(img, (x, FLOOR - 56), (x, FLOOR), (60, 110, 150), 6)
    cv2.putText(img, "Living room (demo)", (440, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1)
    return img


# (開始秒, 結束秒, 動作, 參數)
CARE_SCRIPT = [
    (0, 2, "empty", {}),
    (2, 8, "walk", {"x0": 80, "x1": 300}),
    (8, 9.5, "bend", {"x": 300}),
    (9.5, 12, "walk", {"x0": 300, "x1": CHAIR_X}),
    (12, 19, "sit", {"x": CHAIR_X}),
    (19, 23, "walk", {"x0": CHAIR_X, "x1": 330}),
    (23, 24, "fall", {"x": 330}),
    (24, 33, "lie", {"x": 330}),
    (33, 35, "getup", {"x": 330}),
    (35, 38, "walk", {"x0": 330, "x1": CHAIR_X}),
    (38, 66, "sit", {"x": CHAIR_X}),
]
CARE_TRUTH = [("fall", 23.0, "第 23 秒倒下，躺到第 33 秒"),
              ("inactive", 38.0, "第 38 秒起坐著完全不動")]


def care_frame(t, bg, rng):
    img = bg.copy()
    for start, end, act, a in CARE_SCRIPT:
        if start <= t < end:
            k = (t - start) / (end - start)
            if act == "walk":
                draw_person(img, lerp(a["x0"], a["x1"], k), "walk", phase=t * 6)
            elif act == "bend":
                draw_person(img, a["x"], "bend")
            elif act == "sit":
                draw_person(img, a["x"], "sit")
            elif act == "fall":
                draw_person(img, a["x"], "stand", angle=90 * k)
            elif act == "lie":
                draw_person(img, a["x"], "stand", angle=90)
            elif act == "getup":
                draw_person(img, a["x"], "stand", angle=90 * (1 - k))
            break
    noise = rng.integers(-5, 6, img.shape, dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


# ---------- 門口影片 ----------
def door_background():
    img = np.full((H, W, 3), (190, 200, 205), np.uint8)
    img[FLOOR - 2:] = (135, 140, 145)
    cv2.rectangle(img, (250, 70), (390, FLOOR), (160, 195, 220), -1)   # 大門（淺色木門）
    cv2.rectangle(img, (250, 70), (390, FLOOR), (110, 140, 160), 3)
    cv2.circle(img, (372, 200), 6, (40, 180, 220), -1)
    cv2.putText(img, "Front door (demo)", (450, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1)
    return img


# 每位訪客：[(開始秒, 結束秒, 起點 x, 終點 x)]，x 超出畫面代表不在畫面中
VISITORS = [
    {"color": (60, 60, 150), "path": [(4, 6, -60, 300), (6, 11, 300, 300), (11, 13, 300, 700)]},
    {"color": (150, 80, 50), "path": [(20, 21.5, 700, 330), (21.5, 23.5, 330, 330), (23.5, 25, 330, -60)]},
    {"color": (60, 120, 60), "path": [(33, 35, -60, 280), (35, 39, 280, 280), (39, 40, 280, -60),
                                      (41.5, 42.5, -60, 280), (42.5, 48, 280, 280), (48, 50, 280, 700)]},
]
DOOR_TRUTH = [(4.0, 13.0), (20.0, 25.0), (33.0, 50.0)]


def door_frame(t, bg, rng):
    img = bg.copy()
    for v in VISITORS:
        for start, end, x0, x1 in v["path"]:
            if start <= t < end:
                x = lerp(x0, x1, (t - start) / (end - start))
                draw_person(img, x, "walk" if x0 != x1 else "stand", phase=t * 6, color=v["color"])
                break
    noise = rng.integers(-5, 6, img.shape, dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def write_video(path: Path, seconds: float, bg, frame_fn, seed: int) -> None:
    rng = np.random.default_rng(seed)
    tmp = path.with_suffix(".tmp.mp4")
    vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    if not vw.isOpened():
        raise RuntimeError(f"無法建立影片 {path}")
    for i in range(int(seconds * FPS)):
        vw.write(frame_fn(i / FPS, bg, rng))
    vw.release()
    tmp.replace(path)


def main() -> None:
    write_video(HERE / "care_demo.mp4", 66, care_background(), care_frame, seed=7)
    with open(HERE / "care_demo_truth.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event", "start_sec", "note"])
        w.writerows(CARE_TRUTH)
    write_video(HERE / "door_demo.mp4", 60, door_background(), door_frame, seed=11)
    with open(HERE / "door_demo_truth.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["visit", "start_sec", "end_sec"])
        for i, (s, e) in enumerate(DOOR_TRUTH, 1):
            w.writerow([i, s, e])
    inbox = [{"id": "demo-1001", "at_sec": 20, "author": "女兒小美", "text": "媽，晚上我帶水果回去喔"},
             {"id": "demo-1002", "at_sec": 45, "author": "兒子阿明", "text": "週末帶你去看醫生，記得把健保卡準備好"},
             {"id": "demo-1001", "at_sec": 50, "author": "女兒小美", "text": "媽，晚上我帶水果回去喔"}]
    (HERE / "discord_inbox.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in inbox) + "\n", encoding="utf-8")
    print("已產生：care_demo.mp4（66 秒）、door_demo.mp4（60 秒）、答案檔 2 個、discord_inbox.jsonl")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    main()
