"""標記正確答案：播放影片，車輛從旁邊經過的那一刻按鍵記錄。

按鍵（車頭到達鏡頭旁邊、從畫面離開的那一刻按）：
  1  汽車 car        2  機車 motorcycle
  3  公車 bus        4  貨車 truck
  空白鍵  不分車種
  u       取消上一個標記
  p       暫停／繼續
  a／d    倒退／快轉 3 秒
  ,／.    暫停時往前／往後一格
  q       存檔並離開

用法：python label_events.py videos/我的影片.mp4          存成 videos/我的影片_truth.csv
      python label_events.py 我的影片.mp4 --out 答案.csv

標記時請只看影片，不要看程式的警示結果，避免影響判斷。
"""
import argparse
import csv
import os

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = {ord("1"): "car", ord("2"): "motorcycle", ord("3"): "bus", ord("4"): "truck", ord(" "): ""}


def load_existing(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [(float(r["pass_time"]), r.get("vehicle", "")) for r in csv.DictReader(f)
                if (r.get("pass_time") or "").strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--out", help="答案檔；預設存在影片旁邊，檔名加上 _truth")
    args = parser.parse_args()

    video = args.video if os.path.isabs(args.video) else os.path.join(HERE, args.video)
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit("無法開啟影片")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if args.out:
        out_path = args.out if os.path.isabs(args.out) else os.path.join(HERE, args.out)
    else:
        out_path = os.path.splitext(video)[0] + "_truth.csv"

    marks = load_existing(out_path)
    if marks:
        print(f"讀到之前的 {len(marks)} 個標記，會接著標記（按 u 可以取消最後一個）")
    paused = False
    idx = 0
    ok, frame = cap.read()
    while ok:
        t = idx / fps
        view = frame.copy()
        cv2.rectangle(view, (0, 0), (view.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(view, f"t={t:6.2f}s  marks={len(marks)}  1car 2moto 3bus 4truck SPACE u=undo p=pause a/d q=save",
                    (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        recent = [m for m in marks if 0 <= t - m[0] < 1.0]
        if recent:
            cv2.putText(view, f"MARKED {recent[-1][1]}", (8, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 220, 255), 2)
        cv2.imshow("Label Events", view)
        key = cv2.waitKey(0 if paused else max(1, int(1000 / fps))) & 0xFF

        seek = None
        if key in (ord("q"), 27):
            break
        if key in KEYS:
            marks.append((round(t, 2), KEYS[key]))
            print(f"標記：{t:.2f} 秒 {KEYS[key]}")
        elif key == ord("u") and marks:
            print("取消：{:.2f} 秒".format(marks.pop()[0]))
        elif key == ord("p"):
            paused = not paused
        elif key == ord("a"):
            seek = idx - int(3 * fps)
        elif key == ord("d"):
            seek = idx + int(3 * fps)
        elif key == ord(",") and paused:
            seek = idx - 1
        elif key == ord(".") and paused:
            seek = idx + 1

        if seek is not None:
            idx = max(0, min(total - 1, seek))
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
        elif not paused:
            ok, frame = cap.read()
            idx += 1
    cap.release()
    cv2.destroyAllWindows()

    if not marks:
        print("沒有標記，不存檔")
        return
    if os.path.exists(out_path):
        os.replace(out_path, out_path + ".bak")
        print("舊檔已改名為", os.path.basename(out_path) + ".bak")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["pass_time", "vehicle", "note"])
        for m, vehicle in sorted(marks):
            w.writerow([m, vehicle, ""])
    print(f"已存 {len(marks)} 個標記到 {out_path}")


if __name__ == "__main__":
    main()
