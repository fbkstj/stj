"""產生練習用的後方影片 videos/demo.mp4 與正確答案 videos/demo_truth.csv（還沒錄影前先用它測程式）。

畫面是裝在自行車後方、朝後拍的鏡頭。台灣靠右行駛，超車的車輛會從騎士左邊經過，
在朝後的畫面裡出現在「右半邊」。

內容（共 31 秒）：
   0～ 3 秒  沒有車
   3～10 秒  公車從遠處逼近（相對速度約 22 km/h），約 10.3 秒從旁邊經過 → 應該警示
  12～18 秒  公車跟在後面，距離不變               → 不應警示
  19～23 秒  公車越來越遠                         → 不應警示
  24～29 秒  公車快速逼近（相對速度約 43 km/h），約 28.9 秒經過 → 應該警示

用法：python make_demo_video.py
然後：python rear_alert.py --video videos/demo.mp4 --window
      python evaluate.py --truth videos/demo_truth.csv
或是：python batch_run.py videos
"""
import math
import os

import cv2
import numpy as np
import ultralytics

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "videos")
W, H, FPS, SECONDS = 640, 480, 15, 31
F = 700                 # 鏡頭焦距（像素），約 49 度視角
HORIZON = 200           # 地平線高度（像素）
CAM_HEIGHT = 1.0        # 鏡頭離地高度（公尺）
BUS_WIDTH = 2.5         # 公車寬度（公尺）

# 每台車：(開始秒, 結束秒, 距離函式, 橫向偏移公尺, 是否為真的逼近)
SCENES = [
    (3, None, lambda t: 45 - 6 * (t - 3), 1.8, True),
    (12, 18, lambda t: 12 + 0.3 * math.sin(t * 2), 1.6, False),
    (19, 23, lambda t: 6 + 6 * (t - 19), 1.8, False),
    (24, None, lambda t: 60 - 12 * (t - 24), 2.2, True),
]


def road():
    img = np.full((H, W, 3), (215, 200, 180), dtype=np.uint8)                   # 天空
    img[HORIZON:] = (120, 150, 120)                                               # 路邊草地
    vp = (W // 2, HORIZON)
    cv2.fillPoly(img, [np.array([vp, (W + 900, H), (60, H)])], (105, 105, 110))  # 路面
    cv2.line(img, vp, (60, H), (230, 230, 230), 3)                                # 路邊白線
    for k in range(12):                                                           # 車道虛線
        a, b = k / 12, (k + 0.5) / 12
        p1 = (int(vp[0] + (W + 250 - vp[0]) * a * a), int(HORIZON + (H - HORIZON) * a * a))
        p2 = (int(vp[0] + (W + 250 - vp[0]) * b * b), int(HORIZON + (H - HORIZON) * b * b))
        cv2.line(img, p1, p2, (235, 235, 235), 2)
    return img


def paste(dst, src, w, cx, bottom):
    """把 src 縮放成寬 w，貼到 (cx, bottom)，超出畫面的部分裁掉。"""
    h = int(w * src.shape[0] / src.shape[1])
    x, y = int(cx - w / 2), int(bottom - h)
    x1, y1, x2, y2 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x2 <= x1 or y2 <= y1:
        return
    # 只縮放看得到的部分，車很近時比較快
    sx, sy = src.shape[1] / w, src.shape[0] / h
    part = src[int((y1 - y) * sy):int(math.ceil((y2 - y) * sy)), int((x1 - x) * sx):int(math.ceil((x2 - x) * sx))]
    dst[y1:y2, x1:x2] = cv2.resize(part, (x2 - x1, y2 - y1))


def main():
    img = cv2.imread(os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg"))
    bus = img[229:728, 350:665]          # 範例照片中公車的正面（避開前方的行人）
    base = road()
    os.makedirs(OUT_DIR, exist_ok=True)
    writer = cv2.VideoWriter(os.path.join(OUT_DIR, "demo.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    passes = {}
    rng = np.random.default_rng(0)      # 固定亂數，每個人產生的影片都一樣
    for i in range(SECONDS * FPS):
        t = i / FPS
        frame = base.copy()
        for n, (t0, t1, dist, lateral, real) in enumerate(SCENES):
            if t < t0 or (t1 is not None and t >= t1):
                continue
            d = dist(t)
            if d <= 1.0:                 # 距離 1 公尺以內＝已經從旁邊經過
                passes.setdefault(n, t)
                continue
            paste(frame, bus, int(F * BUS_WIDTH / d), W / 2 + F * lateral / d, HORIZON + F * CAM_HEIGHT / d)
        noise = rng.integers(-4, 5, frame.shape, dtype=np.int16)
        writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))
    writer.release()

    with open(os.path.join(OUT_DIR, "demo_truth.csv"), "w", encoding="utf-8-sig") as f:
        f.write("pass_time,vehicle,note\n")
        for n, (_, _, _, _, real) in enumerate(SCENES):
            if real and n in passes:
                f.write(f"{passes[n]:.2f},bus,練習影片第 {n + 1} 段\n")
    print("已產生 videos/demo.mp4 與 videos/demo_truth.csv")


if __name__ == "__main__":
    main()
