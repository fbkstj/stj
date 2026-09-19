"""長照監護（L5）與智慧監視器（L8）共用：讀影片或攝影機，一張一張交給 process()。"""
from __future__ import annotations

import threading
from datetime import timedelta

from core.clock import iso
from core.media import BlobDetector, open_source, save_jpg
from core.module import Module


class VideoModule(Module):
    interval = 0.1

    def setup(self):
        self.cap = open_source(self.cfg["source"], self.app.root)
        if not self.cap.isOpened():
            raise RuntimeError(f"影像來源打不開：{self.cfg['source']}")
        fps = self.cap.get(5) or 10          # 5 = CAP_PROP_FPS
        self.fps = fps if 1 <= fps <= 60 else 10
        self.interval = 1 / self.fps
        self.frame_no = 0
        self.finished = False
        self.read_fail = 0
        self.started_at = self.clock.now()
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.detector = BlobDetector()
        self.reset_logic()

    def reset_logic(self): ...

    def process(self, t: float, frame): ...

    def video_time(self, t: float):
        return self.started_at + timedelta(seconds=t)

    def step(self):
        if self.finished:
            return
        ok, frame = self.cap.read()
        if not ok:
            if isinstance(self.cfg["source"], str) and not str(self.cfg["source"]).isdigit():
                if self.cfg.get("loop"):
                    self.cap.set(1, 0)            # 1 = CAP_PROP_POS_FRAMES，回到開頭
                    self.frame_no = 0
                    self.started_at = self.clock.now()
                    self.detector = BlobDetector()
                    self.reset_logic()
                else:
                    self.finished = True
                    self.on_finished()
                    self.log.info("示範影片播放完畢")
                return
            self.read_fail += 1
            return
        self.read_fail = 0
        with self.frame_lock:
            self.latest_frame = frame
        self.process(self.frame_no / self.fps, frame)
        self.frame_no += 1

    def on_finished(self): ...

    def teardown(self):
        cap = getattr(self, "cap", None)
        if cap is not None:
            cap.release()

    def check(self):
        if self.finished:
            return True, "示範影片已播放完畢"
        if self.read_fail >= 30:
            return False, "讀不到畫面（攝影機可能斷線）"
        return True, "正常"

    def snapshot(self, prefix: str, frame=None, box=None):
        """存截圖到 data/snapshots；隱私模式時不存，回傳 None。"""
        if self.app.privacy:
            return None
        import cv2
        if frame is None:
            with self.frame_lock:
                frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return None
        frame = frame.copy()
        if box is not None:
            x, y, w, h = box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        self._snap_n = getattr(self, "_snap_n", 0) + 1
        name = f"{prefix}_{self.clock.now():%Y%m%d_%H%M%S}_{self.frame_no:05d}_{self._snap_n}.jpg"
        return str(save_jpg(self.app.snapshot_dir / name, frame))
