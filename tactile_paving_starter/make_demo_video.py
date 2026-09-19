"""產生一支 60 秒的練習影片 demo.mp4（還沒拍到實景時可以先用它練習）。

影片內容：
   0～ 8 秒  導盲磚淨空
   8～28 秒  一台車停在導盲磚上（用 ultralytics 內附的公車照片模擬）
  28～34 秒  淨空
  34～36 秒  行人走過導盲磚（不應該警示）
  36～40 秒  淨空
  40～55 秒  紙箱擋住導盲磚（YOLO 不認得，要靠黃色比例抓到）
  55～60 秒  淨空
同時產生對應的 demo_ground_truth.csv 與 demo_config.json。

用法：python make_demo_video.py
然後：python paving_monitor.py --config demo_config.json
      python evaluate.py --truth demo_ground_truth.csv --state output_demo/state_log.csv --min-event 5
"""
import json
import os

import cv2
import numpy as np
import ultralytics

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SECONDS = 1280, 720, 10, 60
ROI = [[380, 470], [900, 470], [1000, 700], [280, 700]]


def background():
    img = np.full((H, W, 3), (150, 150, 150), dtype=np.uint8)              # 灰色人行道
    cv2.rectangle(img, (0, 0), (W, 300), (190, 170, 140), -1)              # 建築物
    for x in range(-400, W + 400, 90):                                     # 人行道磚縫
        cv2.line(img, (x, 300), (x - 200, H), (135, 135, 135), 2)
    paving = np.zeros((H, W), dtype=np.uint8)
    cv2.fillPoly(paving, [np.array(ROI)], 255)
    tile = np.full_like(img, (0, 205, 255))                                # 黃色導盲磚
    for y in range(480, H, 28):                                            # 導盲磚條紋
        cv2.line(tile, (0, y), (W, y), (0, 175, 225), 4)
    img[paving > 0] = tile[paving > 0]
    return img


def paste(dst, src, x, y):
    h, w = src.shape[:2]
    x2, y2 = min(W, x + w), min(H, y + h)
    x1, y1 = max(0, x), max(0, y)
    if x2 <= x1 or y2 <= y1:
        return
    dst[y1:y2, x1:x2] = src[y1 - y:y2 - y, x1 - x:x2 - x]


def main():
    assets = os.path.join(os.path.dirname(ultralytics.__file__), "assets")
    bus_img = cv2.imread(os.path.join(assets, "bus.jpg"))
    vehicle = cv2.resize(bus_img[228:790, 0:810], (560, 390))            # 公車車身
    person = cv2.resize(bus_img[400:880, 50:245], (130, 320))            # 行人
    base = background()

    out_path = os.path.join(HERE, "demo.mp4")
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(SECONDS * FPS):
        t = i / FPS
        frame = base.copy()
        if 8 <= t < 28:
            paste(frame, vehicle, 360, 320)
        if 34 <= t < 36:
            px = int(200 + (t - 34) / 2 * 800)
            paste(frame, person, px, 390)
        if 40 <= t < 55:
            cv2.rectangle(frame, (330, 420), (960, 700), (60, 110, 160), -1)   # 紙箱
            cv2.rectangle(frame, (330, 420), (960, 700), (40, 80, 120), 4)
        noise = np.random.randint(-6, 7, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        writer.write(frame)
    writer.release()

    with open(os.path.join(HERE, "demo_ground_truth.csv"), "w", encoding="utf-8-sig") as f:
        f.write("start_sec,end_sec,note\n8,28,車輛停放\n40,55,紙箱遮擋\n")

    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.update({"source": "demo.mp4", "roi": ROI, "roi_frame_size": [W, H],
                "vehicle_classes": cfg["vehicle_classes"],
                "baseline_yellow": None, "occupy_seconds": 5, "clear_seconds": 2,
                "voice_alert": False, "output_dir": "output_demo"})
    with open(os.path.join(HERE, "demo_config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("已產生 demo.mp4、demo_ground_truth.csv、demo_config.json")


if __name__ == "__main__":
    main()
