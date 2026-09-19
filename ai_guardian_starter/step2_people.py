"""關卡2:用 YOLO 找出畫面中的人,框起來並顯示人數。 按 q 離開。"""
import sys

import cv2
from ultralytics import YOLO

from tw_text import open_source, put_chinese_text, read_frame

PERSON = 0          # COCO 資料集中「人」的類別編號
CONF = 0.4          # 信心度門檻:越高越嚴格

model = YOLO("yolov8n.pt")
cap = open_source(sys.argv)

while True:
    ok, frame = read_frame(cap)
    if not ok:
        break
    result = model.predict(frame, classes=[PERSON], conf=CONF, imgsz=416, verbose=False)[0]

    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)

    count = len(result.boxes)
    frame = put_chinese_text(frame, f"人數:{count}", (10, 10), (0, 255, 0))
    cv2.imshow("step2 - press q", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
