"""
事件通報:存證(截圖+CSV) → 依等級決定通報方式。

  高:現場警報音 + 畫面紅框,進入「取消窗口」CANCEL_WINDOW_SEC 秒,
      保全沒按 C 取消誤報就自動發出二級通報(LINE)。
  中:直接 LINE 通報。
  低:只記錄不推播。

同一台攝影機的同一種事件,COOLDOWN_SEC 秒內只通報一次,避免洗版。
"""
import csv
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

from line_notify import send_line_alert
from threat_rules import LEVEL_HIGH, LEVEL_MID

COOLDOWN_SEC = 60
CANCEL_WINDOW_SEC = 5
LINE_ENABLED = True
EVENT_DIR = Path(__file__).parent / "events"


def _beep():
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(1800, 250)
            time.sleep(0.1)
    except Exception:
        pass


class Alerter:
    def __init__(self):
        self.last_sent = {}   # (攝影機, 事件種類) -> 時間
        self.pending = []     # 等待取消窗口結束的高風險事件
        # 最近一次的狀態（警示盒顯示用）：(時間, 事件種類)
        self.last_reported = None   # 高風險事件已發出通報
        self.last_cancelled = None  # 保全取消（誤報）
        self.last_notice = None     # 中、低風險事件
        EVENT_DIR.mkdir(exist_ok=True)
        self.csv_path = EVENT_DIR / "events.csv"
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(["時間", "攝影機", "事件", "等級", "說明", "處置", "截圖"])

    def _log(self, ts, cam, ev, action, snap):
        with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([ts, cam, ev.kind, ev.level, ev.detail, action, snap])

    def _save_snapshot(self, cam, ev, frame):
        day_dir = EVENT_DIR / datetime.now().strftime("%Y%m%d")
        day_dir.mkdir(exist_ok=True)
        path = day_dir / f"{datetime.now():%H%M%S}_{cam}_{ev.kind}.jpg"
        ok, buf = cv2.imencode(".jpg", frame)  # cv2.imwrite 不支援中文路徑
        if ok:
            buf.tofile(str(path))
        return str(path.relative_to(EVENT_DIR))

    @staticmethod
    def _message(cam, ev, ts, prefix):
        return f"{prefix}\n時間:{ts}\n地點:{cam}\n事件:{ev.kind}(風險{ev.level})\n說明:{ev.detail}"

    def _send(self, text):
        if LINE_ENABLED:
            send_line_alert(text)
        else:
            print(f"[通報-未啟用LINE]\n{text}", flush=True)

    def handle(self, cam, events, frame, now):
        for ev in events:
            if ev.level != LEVEL_HIGH:
                self.last_notice = (now, ev.kind)   # 事件持續時，警示盒一直顯示「注意」
            key = (cam, ev.kind)
            if now - self.last_sent.get(key, -1e9) < COOLDOWN_SEC:
                continue
            self.last_sent[key] = now
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            snap = self._save_snapshot(cam, ev, frame)
            print(f"[事件] {ts} {cam} {ev.kind}/{ev.level} {ev.detail}", flush=True)

            if ev.level == LEVEL_HIGH:
                threading.Thread(target=_beep, daemon=True).start()
                self.pending.append({"cam": cam, "ev": ev, "ts": ts, "snap": snap,
                                     "deadline": now + CANCEL_WINDOW_SEC})
            elif ev.level == LEVEL_MID:
                self._send(self._message(cam, ev, ts, "【監控通報】"))
                self._log(ts, cam, ev, "LINE通報", snap)
            else:
                self._log(ts, cam, ev, "僅記錄", snap)

    def tick(self, now):
        """每一輪主迴圈呼叫:取消窗口到期的高風險事件升級通報。"""
        for p in [p for p in self.pending if now >= p["deadline"]]:
            self.pending.remove(p)
            self._send(self._message(p["cam"], p["ev"], p["ts"], "🚨【緊急通報】請立即處置"))
            self._log(p["ts"], p["cam"], p["ev"], "二級通報(LINE)", p["snap"])
            self.last_reported = (now, p["ev"].kind)

    def cancel_all(self, now=None):
        """保全按 C（或警示盒的取消鈕）：判定為誤報，取消所有待送出的高風險通報。"""
        if self.pending:
            self.last_cancelled = (time.time() if now is None else now, self.pending[0]["ev"].kind)
        for p in self.pending:
            self._log(p["ts"], p["cam"], p["ev"], "保全取消(誤報)", p["snap"])
            print(f"[取消] {p['cam']} {p['ev'].kind} 已標記為誤報", flush=True)
        self.pending.clear()
