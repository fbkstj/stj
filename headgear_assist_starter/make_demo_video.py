"""產生練習用的影片 demo.mp4 與模擬感測器資料 demo_sensor.csv（還沒做好帽子時先用它測程式）。

內容（共 24 秒）：
   0～ 3 秒  走廊，沒有障礙
   3～ 8 秒  一個人從遠處走近（畫面中越來越大）→ 應該說「前方有人靠近」
   8～11 秒  沒有障礙
  11～15 秒  頭部高度有障礙（影片裡看不出來，只有 ToF 距離變近）→ 應該說「前方有障礙，很近」
  15～18 秒  沒有障礙
  18 秒      按下按鈕 → 應該描述前方
  18～24 秒  前方站著一個人

用法：python make_demo_video.py
然後：python headgear_assist.py --video demo.mp4 --fake-sensor demo_sensor.csv --no-voice --window
"""
import os

import cv2
import numpy as np
import ultralytics

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SECONDS = 640, 480, 15, 24


def corridor():
    img = np.full((H, W, 3), (205, 200, 195), dtype=np.uint8)
    cv2.fillPoly(img, [np.array([[0, H], [W, H], [400, 280], [240, 280]])], (150, 150, 155))   # 地板
    cv2.rectangle(img, (240, 140), (400, 280), (185, 180, 175), -1)                            # 走廊盡頭
    cv2.line(img, (0, 0), (240, 140), (160, 160, 160), 2)
    cv2.line(img, (W, 0), (400, 140), (160, 160, 160), 2)
    return img


def paste(dst, src, cx, bottom):
    h, w = src.shape[:2]
    x, y = int(cx - w / 2), int(bottom - h)
    x1, y1, x2, y2 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x2 > x1 and y2 > y1:
        dst[y1:y2, x1:x2] = src[y1 - y:y2 - y, x1 - x:x2 - x]


def main():
    img = cv2.imread(os.path.join(os.path.dirname(ultralytics.__file__), "assets", "bus.jpg"))
    person = img[400:880, 50:245]
    base = corridor()
    writer = cv2.VideoWriter(os.path.join(HERE, "demo.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    rows = []
    for i in range(SECONDS * FPS):
        t = i / FPS
        frame = base.copy()
        if 3 <= t < 8:
            k = (t - 3) / 5                      # 0 → 1：由遠到近
            ph = int(110 + k * 330)
            pw = int(ph * person.shape[1] / person.shape[0])
            paste(frame, cv2.resize(person, (pw, ph)), W // 2, int(290 + k * 190))
        if t >= 18:
            paste(frame, cv2.resize(person, (150, 370)), W // 2 + 40, 470)
        noise = np.random.randint(-5, 6, frame.shape, dtype=np.int16)
        writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))

        if 11 <= t < 15:
            left, right = int(900 - (t - 11) * 150), int(700 - (t - 11) * 120)
        elif t >= 18:
            left, right = 2500, 1300
        else:
            left, right = -1, -1
        rows.append(f"{t:.2f},{left},{right},{1 if i == 18 * FPS else 0}")
    writer.release()
    with open(os.path.join(HERE, "demo_sensor.csv"), "w", encoding="utf-8") as f:
        f.write("time,left,right,button\n" + "\n".join(rows) + "\n")
    print("已產生 demo.mp4 與 demo_sensor.csv")


if __name__ == "__main__":
    main()
