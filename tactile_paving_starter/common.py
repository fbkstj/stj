"""共用工具：讀寫設定檔、開啟影像來源、建立導盲磚區域遮罩。"""
import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")


def load_config(path=CONFIG_PATH):
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(HERE, path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg, path=CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("已儲存設定：", path)


def parse_source(value):
    """設定檔的 source 可以是攝影機編號（0、1）或影片檔名。"""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    if not os.path.isabs(text):
        text = os.path.join(HERE, text)
    return text


def open_source(cfg, source=None):
    src = parse_source(cfg["source"] if source is None else source)
    if isinstance(src, int):
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(src)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.get("camera_width", 1280))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.get("camera_height", 720))
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        is_video = False
    else:
        if not os.path.exists(src):
            raise FileNotFoundError(f"找不到影片檔：{src}")
        cap = cv2.VideoCapture(src)
        is_video = True
    if not cap.isOpened():
        raise RuntimeError(f"無法開啟影像來源：{src}（攝影機被其他程式占用？編號不對？）")
    return cap, is_video


def scaled_roi(cfg, frame_shape):
    """依目前畫面大小縮放導盲磚區域的座標。"""
    pts = cfg.get("roi") or []
    if len(pts) < 3:
        return None
    h, w = frame_shape[:2]
    rw, rh = cfg.get("roi_frame_size") or [w, h]
    sx, sy = w / float(rw), h / float(rh)
    return np.array([[int(x * sx), int(y * sy)] for x, y in pts], dtype=np.int32)


def roi_mask(frame_shape, polygon):
    mask = np.zeros(frame_shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon], 255)
    return mask


def yellow_ratio(frame, mask, cfg):
    """導盲磚區域裡，看得到黃色的比例（0～1）。"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array(cfg["hsv_lower"]), np.array(cfg["hsv_upper"]))
    inside = cv2.countNonZero(mask)
    if inside == 0:
        return 0.0
    return cv2.countNonZero(cv2.bitwise_and(yellow, mask)) / float(inside)
