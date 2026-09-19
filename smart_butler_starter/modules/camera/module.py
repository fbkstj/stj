"""L8 智慧監視器：偵測門口有人，合併成「來訪」，記錄時間與截圖；可查詢某段時間的訪客。"""
from __future__ import annotations

from core.video_module import VideoModule
from modules.camera.visits import VISIT_SCHEMA, VisitTracker, in_night, save_visit


class CameraModule(VideoModule):
    name = "camera"
    title = "智慧監視器"

    def setup(self):
        self.app.store.executescript(VISIT_SCHEMA)
        super().setup()

    def reset_logic(self):
        self.tracker = VisitTracker(self.cfg["merge_gap_sec"], self.cfg["min_visit_sec"])
        self.last_box = None

    def process(self, t, frame):
        box = self.detector.detect(frame)
        self.last_box = box
        visit = self.tracker.update(t, box, None if self.app.privacy else frame)
        if visit:
            self.record(visit)

    def on_finished(self):
        visit = self.tracker.close()
        if visit:
            self.record(visit)

    def record(self, v):
        start, end = self.video_time(v["start"]), self.video_time(v["last_seen"])
        night = in_night(start, self.cfg["night_start"], self.cfg["night_end"])
        snap = None
        if not self.app.privacy and v["best_frame"] is not None:
            snap = self.snapshot("visit", v["best_frame"], v["best_box"])
        vid = save_visit(self.app.store, start, end, v["seconds"], snap, night)
        when = start.strftime("%H:%M:%S")
        if night:
            self.publish("visit", "warn", f"深夜有人在門口：{when} 起停留 {v['seconds']:g} 秒", snap, visit_id=vid)
        else:
            self.publish("visit", "info", f"有訪客：{when} 起停留 {v['seconds']:g} 秒", snap, visit_id=vid)


if __name__ == "__main__":
    import argparse
    import cv2
    from core import console
    from core.media import BlobDetector
    console.setup()
    p = argparse.ArgumentParser(description="分析門口影片的來訪次數（不開攝影機）")
    p.add_argument("video", nargs="?", default="demo/door_demo.mp4")
    p.add_argument("--merge-gap", type=float, default=3.0)
    a = p.parse_args()
    cap, det, tr, i = cv2.VideoCapture(a.video), BlobDetector(), VisitTracker(a.merge_gap), 0
    fps, n = cap.get(cv2.CAP_PROP_FPS) or 10, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        v = tr.update(i / fps, det.detect(f))
        if v:
            n += 1
            print(f"來訪 {n}：第 {v['start']:.1f}～{v['last_seen']:.1f} 秒")
        i += 1
    v = tr.close()
    if v:
        n += 1
        print(f"來訪 {n}：第 {v['start']:.1f}～{v['last_seen']:.1f} 秒")
    print(f"共 {n} 次來訪")
