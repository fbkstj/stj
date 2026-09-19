"""L2 事件紀錄：所有事件存進 SQLite（data/aina.db），可以依時間查詢、匯出 CSV。

資料表 events 的欄位：
  id 編號、time 時間（台北時間字串）、source 來源模組、kind 類型、level 等級、
  message 內容、attachment 附件路徑、data 其他資料（JSON 文字）
"""
from __future__ import annotations

import csv
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from core.clock import iso
from core.events import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    attachment TEXT,
    data TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(time);
"""


def _t(value) -> str | None:
    if value is None:
        return None
    return iso(value) if isinstance(value, datetime) else str(value)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- 給其他模組建立自己的資料表 ----
    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def executescript(self, sql: str) -> None:
        with self.lock:
            self.conn.executescript(sql)
            self.conn.commit()

    def fetch_all(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    # ---- 事件 ----
    def save_event(self, event: Event) -> None:
        """EventBus 的訂閱者：每個事件都寫進資料庫，並填回編號。"""
        cur = self.execute(
            "INSERT INTO events(time, source, kind, level, message, attachment, data) VALUES (?,?,?,?,?,?,?)",
            (event.time, event.source, event.kind, event.level, event.message, event.attachment,
             json.dumps(event.data, ensure_ascii=False) if event.data else None))
        event.id = cur.lastrowid

    def query(self, start=None, end=None, source=None, kind=None, level=None, limit=None,
              newest_first=False) -> list[dict]:
        sql, params = "SELECT * FROM events WHERE 1=1", []
        for col, op, val in (("time", ">=", _t(start)), ("time", "<", _t(end)),
                             ("source", "=", source), ("level", "=", level)):
            if val:
                sql += f" AND {col} {op} ?"
                params.append(val)
        if kind:
            kinds = [kind] if isinstance(kind, str) else list(kind)
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params += kinds
        sql += " ORDER BY time DESC, id DESC" if newest_first else " ORDER BY time, id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self.fetch_all(sql, params)
        for r in rows:
            r["data"] = json.loads(r["data"]) if r["data"] else {}
        return rows

    def count(self, start=None, end=None, **filters) -> int:
        return len(self.query(start, end, **filters))

    def export_csv(self, path: Path | str, start=None, end=None, **filters) -> int:
        """匯出 CSV；用 utf-8-sig（有 BOM），Excel 打開中文才不會亂碼。回傳筆數。"""
        rows = self.query(start, end, **filters)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["編號", "時間", "來源", "類型", "等級", "內容", "附件"])
            for r in rows:
                w.writerow([r["id"], r["time"], r["source"], r["kind"], r["level"], r["message"], r["attachment"] or ""])
        return len(rows)

    def delete_events_before(self, when, kinds=None) -> int:
        sql, params = "DELETE FROM events WHERE time < ?", [_t(when)]
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params += list(kinds)
        return self.execute(sql, params).rowcount

    def close(self) -> None:
        with self.lock:
            self.conn.close()
