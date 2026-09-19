"""共用小工具:在 OpenCV 畫面上寫中文(cv2.putText 不支援中文)。"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 24)  # 微軟正黑體


def put_chinese_text(frame, text, xy, bgr=(255, 255, 255)):
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(img).text(xy, text, font=FONT, fill=bgr[::-1],
                             stroke_width=2, stroke_fill=(0, 0, 0))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def open_source(argv):
    """沒給參數就開 0 號攝影機;給數字開對應攝影機;給檔名開影片。"""
    src = argv[1] if len(argv) > 1 else "0"
    if src.isdigit():
        return cv2.VideoCapture(int(src), cv2.CAP_DSHOW)
    return cv2.VideoCapture(src)


def read_frame(cap, max_width=960):
    """讀一張畫面,太大就等比例縮小(高解析度網路攝影機字會太小、運算也慢)。"""
    ok, frame = cap.read()
    if ok and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
    return ok, frame
