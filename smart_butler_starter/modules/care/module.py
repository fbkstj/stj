"""L5 長照監護模組：從影像偵測跌倒（緊急）與長時間沒有活動（注意）。"""
from __future__ import annotations

from core.video_module import VideoModule
from modules.care.monitor import CareMonitor


class CareModule(VideoModule):
    name = "care"
    title = "長照監護"

    def reset_logic(self):
        c = self.cfg
        self.monitor = CareMonitor(c["fall_sec"], c["inactive_min"], c["move_px"], c["activity_every_min"])
        self.last_box = None

    def process(self, t, frame):
        box = self.detector.detect(frame)
        self.last_box = box
        for kind, level, message in self.monitor.update(t, box):
            attachment = self.snapshot("fall", frame, box) if kind == "fall" else None
            self.publish(kind, level, message, attachment, video_sec=round(t, 1))


def analyze_video(path, fall_sec=3.0, inactive_min=60.0, move_px=25.0, activity_every_min=5.0):
    """不經過主程式，直接分析整支影片（測試與調參數用）。回傳 [(秒數, kind, level, message)]。"""
    import cv2
    from core.media import BlobDetector
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    det, mon = BlobDetector(), CareMonitor(fall_sec, inactive_min, move_px, activity_every_min)
    found, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = i / fps
        for kind, level, msg in mon.update(t, det.detect(frame)):
            found.append((round(t, 1), kind, level, msg))
        i += 1
    cap.release()
    return found


if __name__ == "__main__":
    import argparse
    from core import console
    console.setup()
    p = argparse.ArgumentParser(description="分析一支影片的跌倒與久未活動（不開攝影機）")
    p.add_argument("video", nargs="?", default="demo/care_demo.mp4")
    p.add_argument("--fall-sec", type=float, default=3.0)
    p.add_argument("--inactive-min", type=float, default=0.2)
    a = p.parse_args()
    for t, kind, level, msg in analyze_video(a.video, a.fall_sec, a.inactive_min):
        if kind != "activity":
            print(f"第 {t:5.1f} 秒  {level:6s} {kind:9s} {msg}")
