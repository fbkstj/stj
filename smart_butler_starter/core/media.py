"""影像共用工具：開啟影像來源、存截圖、簡易人物偵測（示範用）。

中文路徑注意：cv2.imread／cv2.imwrite 不支援中文路徑，這裡改用 imencode＋tofile。
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def open_source(source, root: Path):
    """source 是影片路徑或攝影機編號。攝影機要經過同意才能使用（見 docs/專案規則.md）。"""
    if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        return cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
    p = Path(source)
    p = p if p.is_absolute() else root / p
    if not p.exists():
        raise FileNotFoundError(f"找不到影片 {p}（請先執行 1_make_demo.bat 產生示範影片）")
    return cv2.VideoCapture(str(p))


def save_jpg(path: Path, frame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise IOError("截圖編碼失敗")
    buf.tofile(str(path))
    return path


def read_jpg(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


class BlobDetector:
    """示範用的簡易人物偵測：和「空場景」背景相減，找出最大的一塊，回傳外框。

    示範影片是程式畫的，背景固定，用這個方法就夠了。真實攝影機請改用
    MediaPipe 姿態偵測或 YOLO（手冊 L5、L8），但輸出一樣是「人的外框」，後面的判斷不用改。
    """

    def __init__(self, threshold: int = 35, min_area: int = 1500, learn_frames: int = 5):
        self.threshold = threshold
        self.min_area = min_area
        self.learn_frames = learn_frames
        self.background = None
        self._seen = 0

    def detect(self, frame):
        """回傳 (x, y, w, h) 或 None。前幾張畫面拿來當背景（影片開頭要是空場景）。"""
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if self._seen < self.learn_frames:
            self._seen += 1
            self.background = gray.astype(np.float32) if self.background is None else \
                cv2.addWeighted(self.background, 0.5, gray.astype(np.float32), 0.5, 0)
            return None
        diff = cv2.absdiff(gray, cv2.convertScaleAbs(self.background))
        _, mask = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) < self.min_area:
            return None
        return cv2.boundingRect(biggest)
