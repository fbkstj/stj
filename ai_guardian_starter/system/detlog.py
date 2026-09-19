"""
偵測紀錄（*_dets.csv）的讀寫，以及共用的資料夾位置。

為什麼要把「YOLO 找到什麼」先存起來？
  YOLO 分析一支影片要好幾分鐘，但規則判斷只要不到一秒。
  偵測結果存成 CSV 之後，改門檻做實驗時只要「重播」規則，不必重新跑 YOLO。

每一列是一個偵測框；某個時間點什麼都沒找到時，寫一列 cls = -1。
  t        影片中的秒數
  frame_h  畫面高度（奔逃規則要用）
  frame_w  畫面寬度
  cls      COCO 類別（0 人、43 刀、34 球棒、76 剪刀）
  conf     信心度
  x1,y1,x2,y2  框的座標（像素）
"""
import csv
from pathlib import Path

from threat_rules import Detection

ROOT = Path(__file__).resolve().parent.parent      # 程式包資料夾
VIDEOS = ROOT / "videos"
LOGS = ROOT / "logs"
OUTPUT = ROOT / "output"
VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv")

FIELDS = ["t", "frame_h", "frame_w", "cls", "conf", "x1", "y1", "x2", "y2"]


def resolve(path):
    """相對路徑以程式包資料夾為準（bat 檔從 system 資料夾執行）。"""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p.resolve()
    return (ROOT / p).resolve()


def dets_path_for(video):
    video = Path(video)
    return video.with_name(video.stem + "_dets.csv")


def truth_path_for(video):
    video = Path(video)
    stem = video.stem[:-5] if video.stem.endswith("_dets") else video.stem
    return video.with_name(stem + "_truth.csv")


def write_dets(path, frames):
    """frames：[(t, frame_h, frame_w, [Detection, ...]), ...]"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for t, h, fw, dets in frames:
            if not dets:
                w.writerow([f"{t:.3f}", h, fw, -1, 0, 0, 0, 0, 0])
            for d in dets:
                w.writerow([f"{t:.3f}", h, fw, d.cls, f"{d.conf:.3f}", *(f"{v:.1f}" for v in d.box)])


def read_dets(path):
    frames = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            t = float(r["t"])
            if not frames or abs(frames[-1][0] - t) > 1e-6:
                frames.append((t, int(float(r["frame_h"])), int(float(r["frame_w"])), []))
            cls = int(r["cls"])
            if cls >= 0:
                box = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
                frames[-1][3].append(Detection(cls, float(r["conf"]), box))
    return frames
