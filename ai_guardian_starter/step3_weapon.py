"""關卡3:偵測危險物品,並判斷是不是「拿在人手上」。 按 q 離開。

練習時請用「剪刀」代替刀械(COCO 類別 76),安全又容易取得。
"""
import sys

import cv2
from ultralytics import YOLO

from tw_text import open_source, put_chinese_text, read_frame

PERSON = 0
WEAPONS = {43: "刀子", 34: "球棒", 76: "剪刀"}
CONF = 0.3


def expand(box, ratio):
    """把框往外擴大一點(手拿東西時,物品常常在人的框邊緣外)。"""
    x1, y1, x2, y2 = box
    dw, dh = (x2 - x1) * ratio, (y2 - y1) * ratio
    return x1 - dw, y1 - dh, x2 + dw, y2 + dh


def overlap(a, b):
    """兩個框有沒有重疊。"""
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


model = YOLO("yolov8n.pt")
cap = open_source(sys.argv)

while True:
    ok, frame = read_frame(cap)
    if not ok:
        break
    result = model.predict(frame, classes=[PERSON, *WEAPONS], conf=CONF,
                           imgsz=416, verbose=False)[0]
    people, weapons = [], []
    for box in result.boxes:
        cls = int(box.cls[0])
        xyxy = tuple(box.xyxy[0].tolist())
        (people if cls == PERSON else weapons).append((cls, xyxy))

    held = False
    for cls, w in weapons:
        in_hand = any(overlap(w, expand(p, 0.15)) for _, p in people)
        held = held or in_hand
        color = (0, 0, 255) if in_hand else (0, 200, 255)
        x1, y1, x2, y2 = map(int, w)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        label = WEAPONS[cls] + ("(手持!)" if in_hand else "")
        frame = put_chinese_text(frame, label, (x1, max(y1 - 30, 0)), color)

    for _, p in people:
        x1, y1, x2, y2 = map(int, p)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)

    status = "危險:有人手持危險物品" if held else "正常"
    frame = put_chinese_text(frame, status, (10, 10), (0, 0, 255) if held else (0, 255, 0))
    cv2.imshow("step3 - press q", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
