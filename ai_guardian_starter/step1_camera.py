"""關卡1:打開攝影機,顯示即時畫面。 按 q 離開。
用法:python step1_camera.py        (0 號攝影機)
      python step1_camera.py 1      (1 號攝影機)
      python step1_camera.py test.mp4
"""
import sys

import cv2

from tw_text import open_source, put_chinese_text, read_frame

cap = open_source(sys.argv)
if not cap.isOpened():
    print("打不開影像來源:確認攝影機有接上、沒被其他程式(Teams、LINE)占用")
    sys.exit()

while True:
    ok, frame = read_frame(cap)
    if not ok:
        break
    h, w = frame.shape[:2]
    frame = put_chinese_text(frame, f"解析度 {w}x{h}", (10, 10))
    cv2.imshow("step1 - press q", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
