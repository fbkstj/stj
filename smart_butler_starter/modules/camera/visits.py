"""L8 來訪合併規則與查詢（不碰影像，方便測試）。

一次來訪只記一筆：人連續出現的畫面合併成一次；中間消失不超過 merge_gap_sec 秒仍算同一次。
每次來訪保留「人最大（最清楚）」的那一張畫面當截圖。
"""
from __future__ import annotations

from core.clock import iso

VISIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    seconds REAL NOT NULL,
    snapshot TEXT,
    night INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_visits_start ON visits(start);
"""


class VisitTracker:
    def __init__(self, merge_gap_sec=3.0, min_visit_sec=1.0):
        self.merge_gap = merge_gap_sec
        self.min_visit = min_visit_sec
        self.current = None      # {"start", "last_seen", "best_area", "best_frame", "best_box"}

    def update(self, t: float, box, frame=None):
        """回傳剛結束的一次來訪（dict）或 None。"""
        if box is not None:
            area = box[2] * box[3]
            if self.current is None:
                self.current = {"start": t, "last_seen": t, "best_area": 0, "best_frame": None, "best_box": None}
            c = self.current
            c["last_seen"] = t
            if area > c["best_area"]:
                c["best_area"], c["best_box"] = area, box
                c["best_frame"] = None if frame is None else frame.copy()
            return None
        if self.current and t - self.current["last_seen"] > self.merge_gap:
            return self.close()
        return None

    def close(self):
        c, self.current = self.current, None
        if c is None or c["last_seen"] - c["start"] < self.min_visit:
            return None
        c["seconds"] = round(c["last_seen"] - c["start"], 1)
        return c


def in_night(dt, start: str, end: str) -> bool:
    hm = dt.strftime("%H:%M")
    return (start <= hm or hm < end) if start > end else (start <= hm < end)


def save_visit(store, start_dt, end_dt, seconds, snapshot, night) -> int:
    cur = store.execute("INSERT INTO visits(start, end, seconds, snapshot, night) VALUES (?,?,?,?,?)",
                        (iso(start_dt), iso(end_dt), seconds, snapshot, int(night)))
    return cur.lastrowid


def visits(store, start, end) -> list[dict]:
    """查詢某段時間的來訪清單（管理介面「訪客查詢」用）。"""
    store.executescript(VISIT_SCHEMA)
    s = start if isinstance(start, str) else iso(start)
    e = end if isinstance(end, str) else iso(end)
    return store.fetch_all("SELECT * FROM visits WHERE start >= ? AND start < ? ORDER BY start", (s, e))
