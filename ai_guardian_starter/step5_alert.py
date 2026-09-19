"""關卡5:通報流程——截圖存證、寫入紀錄檔、5 秒取消窗口。

警示成立後:
  1. 截圖存到 events 資料夾,並寫一筆到 events.csv
  2. 發出嗶聲,畫面顯示倒數 5 秒
  3. 5 秒內按 c = 誤報取消;沒按 = 正式通報(關卡6 會改成發 LINE)
按 q 離開。
"""
import csv
import sys
import time
import winsound
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

from guard_core import SustainedFlag, find_held_weapons
from tw_text import open_source, put_chinese_text, read_frame

SUSTAIN_SEC = 0.6
CANCEL_SEC = 5
COOLDOWN_SEC = 30          # 通報後冷卻時間,避免同一事件一直重複通報
EVENT_DIR = Path("events")
EVENT_DIR.mkdir(exist_ok=True)
CSV_PATH = EVENT_DIR / "events.csv"


def write_log(ts, what, action, snap):
    new_file = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:  # utf-8-sig:Excel 開啟不亂碼
        w = csv.writer(f)
        if new_file:
            w.writerow(["時間", "事件", "處置", "截圖"])
        w.writerow([ts, what, action, snap])


def report(ts, what):
    """正式通報。關卡6 把這裡換成 send_line()。"""
    print(f"【緊急通報】{ts} 偵測到有人手持{what},請保全立即前往處置")


model = YOLO("yolov8n.pt")
cap = open_source(sys.argv)
flag = SustainedFlag(SUSTAIN_SEC)
pending = None             # 等待取消窗口中的事件
last_report = -1e9

while True:
    ok, frame = read_frame(cap)
    if not ok:
        break
    now = time.time()
    held, people = find_held_weapons(model, frame)
    alarm = flag.update(bool(held), now)

    if alarm and pending is None and now - last_report > COOLDOWN_SEC:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snap = EVENT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(str(snap), frame)
        pending = {"ts": ts, "what": "、".join(held), "snap": str(snap), "deadline": now + CANCEL_SEC}
        last_report = now
        winsound.Beep(1800, 300)

    if pending:
        remain = pending["deadline"] - now
        if remain <= 0:
            report(pending["ts"], pending["what"])
            write_log(pending["ts"], pending["what"], "已通報", pending["snap"])
            pending = None
        else:
            frame = put_chinese_text(frame, f"{remain:.1f} 秒後通報,誤報請按 c",
                                     (10, 50), (0, 0, 255))

    status = "警示成立" if alarm else f"監控中  人數 {people}"
    frame = put_chinese_text(frame, status, (10, 10), (0, 0, 255) if alarm else (0, 255, 0))
    cv2.imshow("step5 - c=cancel q=quit", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("c") and pending:
        write_log(pending["ts"], pending["what"], "誤報取消", pending["snap"])
        print("已取消:標記為誤報")
        pending = None
    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
