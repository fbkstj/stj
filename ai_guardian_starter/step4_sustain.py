"""關卡4:防誤報——危險物品要「持續」出現一段時間才算數。 按 q 離開。

觀察重點:把剪刀快速晃過鏡頭,進度條沒跑滿就不會觸發警示。
"""
import sys
import time

import cv2
from ultralytics import YOLO

from guard_core import SustainedFlag, find_held_weapons
from tw_text import open_source, put_chinese_text, read_frame

SUSTAIN_SEC = 0.6   # 試試看改成 0、0.6、2,比較誤報與反應速度

model = YOLO("yolov8n.pt")
cap = open_source(sys.argv)
flag = SustainedFlag(SUSTAIN_SEC)

while True:
    ok, frame = read_frame(cap)
    if not ok:
        break
    now = time.time()
    held, people = find_held_weapons(model, frame)
    alarm = flag.update(bool(held), now)

    # 畫進度條
    bar_w = int(300 * flag.progress(now))
    cv2.rectangle(frame, (10, 50), (310, 70), (80, 80, 80), -1)
    cv2.rectangle(frame, (10, 50), (10 + bar_w, 70), (0, 0, 255), -1)

    if alarm:
        cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 12)
        text = f"警示成立:手持{'、'.join(held) or '危險物品'}"
    else:
        text = f"監控中  人數 {people}"
    frame = put_chinese_text(frame, text, (10, 10), (0, 0, 255) if alarm else (0, 255, 0))
    cv2.imshow("step4 - press q", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
