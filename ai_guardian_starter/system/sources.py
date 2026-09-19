"""
影像來源讀取:每個來源一條背景執行緒,只保留「最新一張」畫面,
主程式要推論時直接拿最新的,不會因為某台攝影機卡住而拖慢其他台。
"""
import os
import threading
import time
import urllib.request

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"  # 必須在 import cv2 之前

import cv2
import numpy as np

RECONNECT_DELAY_SEC = 3


class FrameSource:
    def __init__(self, cfg):
        self.name = cfg["name"]
        self.type = cfg["type"]
        self.src = cfg["src"]
        self.interval = cfg.get("interval", 2)
        self.frame = None
        self.frame_id = 0          # 每來一張新畫面就 +1,主程式用來判斷要不要重新推論
        self.online = False
        self._lock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop = True

    def latest(self):
        with self._lock:
            return self.frame_id, self.frame

    def _put(self, frame):
        with self._lock:
            self.frame = frame
            self.frame_id += 1
        self.online = True

    def _run(self):
        try:
            if self.type == "image":
                self._run_image()
            elif self.type == "http_snapshot":
                self._run_snapshot()
            else:
                self._run_capture()
        except Exception as e:  # 單一來源出錯不影響其他來源
            print(f"[{self.name}] 來源執行緒結束:{type(e).__name__}: {e}", flush=True)
            self.online = False

    def _open(self):
        if self.type == "webcam":
            return cv2.VideoCapture(int(self.src), cv2.CAP_DSHOW)
        if self.type == "rtsp":
            return cv2.VideoCapture(self.src, cv2.CAP_FFMPEG)
        return cv2.VideoCapture(self.src)  # video

    def _run_capture(self):
        cap = self._open()
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        while not self._stop:
            ok, frame = cap.read()
            if not ok:
                if self.type == "video":  # 影片播完從頭開始
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                self.online = False
                print(f"[{self.name}] 讀取失敗,{RECONNECT_DELAY_SEC} 秒後重連", flush=True)
                cap.release()
                time.sleep(RECONNECT_DELAY_SEC)
                cap = self._open()
                continue
            self._put(frame)
            if self.type == "video":  # 影片檔依原始速度播放,不然會瞬間跑完
                time.sleep(1 / fps)
        cap.release()

    def _run_image(self):
        frame = cv2.imdecode(np.fromfile(self.src, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(self.src)
        while not self._stop:
            self._put(frame.copy())
            time.sleep(0.2)

    def _run_snapshot(self):
        while not self._stop:
            try:
                with urllib.request.urlopen(self.src, timeout=8) as resp:
                    data = np.frombuffer(resp.read(), dtype=np.uint8)
                frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
                if frame is not None:
                    self._put(frame)
            except OSError as e:
                self.online = False
                print(f"[{self.name}] 快照抓取失敗:{e}", flush=True)
            time.sleep(self.interval)
