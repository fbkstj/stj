"""
產生練習資料：不用攝影機、不用拍影片，就能練習「評估成效」與「調整參數」。

產生：
  videos/demo_dets.csv    模擬 YOLO 對一段 3 分鐘穿堂演練的偵測結果（固定亂數，每個人的結果都一樣）
  videos/demo_truth.csv   這段演練的正確答案

情境內容見 demo_scenes.py 的 SCENES。
用法：python make_demo_detections.py
"""
import csv
import sys

import demo_scenes
import detlog


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    detlog.VIDEOS.mkdir(parents=True, exist_ok=True)
    frames = demo_scenes.build_frames()
    dets_path = detlog.VIDEOS / "demo_dets.csv"
    detlog.write_dets(dets_path, frames)
    truth_path = detlog.VIDEOS / "demo_truth.csv"
    with open(truth_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["kind", "start", "end", "note"])
        for kind, start, end, note in demo_scenes.TRUTH:
            w.writerow([kind, start, end, note])
    print(f"已產生 {dets_path.name}（{len(frames)} 筆時間點）與 {truth_path.name}（{len(demo_scenes.TRUTH)} 件事）")
    print("情境：")
    for t0, t1, text in demo_scenes.SCENES:
        print(f"  {t0:>3}～{t1:>3} 秒  {text}")


if __name__ == "__main__":
    main()
