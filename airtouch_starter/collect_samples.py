"""收集自己的手勢樣本：對著鏡頭比手勢，按數字鍵錄 2 秒的關節點，存到 data/samples_<標籤>.csv。

按鍵（按下後倒數 1 秒，接著錄 2 秒，錄的時候可以慢慢轉動手腕、前後移動）：
  1 手掌張開   2 食指向右   3 食指向左   4 大拇指朝上   5 大拇指朝下
  6 剪刀手     7 握拳       0 沒有指令（抓頭、揮手、拿杯子等日常動作）
  q 結束

用法：python collect_samples.py --tag 王小明_近_白天
標籤建議寫「人_距離_光線」，評估時會分開計算，找出哪種情況最容易認錯。
每個手勢建議每種情況錄 3 次以上；只存關節點座標，不存照片。
"""
import argparse
import csv
import os
import time
from collections import Counter

import cv2

from airtouch import Painter, draw_hand, load_model, make_detector, resolve
import gestures

KEYS = {ord("1"): "open_palm", ord("2"): "point_right", ord("3"): "point_left", ord("4"): "thumb_up",
        ord("5"): "thumb_down", ord("6"): "v_sign", ord("7"): "fist", ord("0"): "none"}


def main():
    import json
    import mediapipe as mp

    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="我的樣本")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    with open(resolve(args.config), encoding="utf-8") as f:
        cfg = json.load(f)

    detector = make_detector(load_model(resolve(cfg["model_path"])), cfg)
    cam = cfg["camera"]
    cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(cam)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["camera_width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["camera_height"])
    if not cap.isOpened():
        raise SystemExit("無法開啟鏡頭")

    os.makedirs(resolve("data"), exist_ok=True)
    safe_tag = "".join(c if c.isalnum() or c in "_-" else "_" for c in args.tag)
    out = resolve(os.path.join("data", f"samples_{safe_tag}.csv"))
    new_file = not os.path.exists(out)
    f = open(out, "a", newline="", encoding="utf-8-sig")
    w = csv.writer(f)
    if new_file:
        w.writerow(["label", "tag", "width", "height"] + [f"{a}{i}" for i in range(21) for a in "xy"])

    painter = Painter()
    counts = Counter()
    label, phase_end, phase = None, 0.0, "idle"
    start = time.time()
    last_ts = -1
    print(f"樣本會存到 {out}")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        if cfg.get("mirror", True):
            frame = cv2.flip(frame, 1)
        h, wid = frame.shape[:2]
        ts = max(int((time.time() - start) * 1000), last_ts + 1)
        last_ts = ts
        res = detector.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), ts)
        pts = None
        if res.hand_landmarks:
            hands = [gestures.to_pixels([(p.x, p.y) for p in lm], wid, h) for lm in res.hand_landmarks]
            pts = max(hands, key=lambda q: ((q[0] - q[9]) ** 2).sum())
            draw_hand(frame, pts, 0, False)

        now = time.time()
        if phase == "countdown" and now >= phase_end:
            phase, phase_end = "record", now + 2.0
        elif phase == "record":
            if pts is not None:
                w.writerow([label, args.tag, wid, h] + [round(v, 5) for p in pts for v in (p[0] / wid, p[1] / h)])
                counts[label] += 1
            if now >= phase_end:
                phase = "idle"
                f.flush()

        cv2.rectangle(frame, (0, 0), (wid, 62), (40, 40, 40), -1)
        name = gestures.GESTURE_NAMES.get(label, "")
        status = {"idle": "按數字鍵開始錄：1 張開 2 右指 3 左指 4 讚 5 倒讚 6 剪刀 7 握拳 0 無指令",
                  "countdown": f"準備比「{name}」… {phase_end - now:.1f}",
                  "record": f"錄製「{name}」中… {phase_end - now:.1f}"}[phase]
        done = "  ".join(f"{gestures.SHORT_NAMES[k]}{v}" for k, v in counts.items())
        painter.texts(frame, [(status, (8, 6), 16, (255, 255, 255)),
                              (f"標籤：{args.tag}   本次已錄：{done or '無'}", (8, 34), 16, (255, 230, 120))])
        if phase == "record":
            cv2.circle(frame, (wid - 24, 90), 12, (0, 0, 255), -1)
        cv2.imshow("AirTouch Collect", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if phase == "idle" and key in KEYS:
            label, phase, phase_end = KEYS[key], "countdown", now + 1.0

    f.close()
    cap.release()
    cv2.destroyAllWindows()
    detector.close()
    print("本次收集：", {gestures.GESTURE_NAMES[k]: v for k, v in counts.items()})
    print("樣本檔：", out)


if __name__ == "__main__":
    main()
