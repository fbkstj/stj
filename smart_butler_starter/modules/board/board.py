"""L7 留言板：網頁與 Discord 雙向同步。

避免迴圈的關鍵：每則留言都記下「對應的 Discord 訊息編號」（discord_id，資料庫設為不可重複）。
- 網頁留言 → 送到 Discord，拿回訊息編號存起來
- 讀到 Discord 新訊息 → 如果這個編號已經在資料庫（是我們自己送的，或已經同步過）就跳過
所以同一則訊息只會出現一次，重新啟動也不會重送。
"""
from __future__ import annotations

import logging
import sqlite3

from core.clock import iso

log = logging.getLogger("board")

BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,          -- web 或 discord
    discord_id TEXT UNIQUE         -- 對應的 Discord 訊息編號；還沒送出時是空的
);
"""


class Board:
    def __init__(self, store, clock, send=None, channel="留言板", publish=None):
        """send(channel, text) 回傳 Discord 訊息編號；送不出去時丟出例外。"""
        self.store = store
        self.clock = clock
        self.send = send
        self.channel = channel
        self.publish = publish
        store.executescript(BOARD_SCHEMA)

    def post(self, author: str, text: str) -> dict:
        """網頁（或管理介面）新增留言，並嘗試同步到 Discord。"""
        author, text = author.strip()[:20] or "家人", text.strip()[:500]
        if not text:
            raise ValueError("留言內容不可空白")
        cur = self.store.execute("INSERT INTO messages(time, author, text, source) VALUES (?,?,?,'web')",
                                 (iso(self.clock.now()), author, text))
        msg_id = cur.lastrowid
        self.sync_pending()
        if self.publish:
            self.publish("board", "info", f"留言板新留言（{author}）", message_id=msg_id)
        return self.get(msg_id)

    def sync_pending(self) -> int:
        """把還沒送到 Discord 的網頁留言送出（斷網時會留到下次）。"""
        if not self.send:
            return 0
        n = 0
        for m in self.store.fetch_all("SELECT * FROM messages WHERE source='web' AND discord_id IS NULL ORDER BY id"):
            try:
                did = self.send(self.channel, f"💬 {m['author']}：{m['text']}")
            except Exception as e:
                log.info("留言暫時無法同步到 Discord：%s", e)
                break
            self.store.execute("UPDATE messages SET discord_id=? WHERE id=?", (did or f"sent-{m['id']}", m["id"]))
            n += 1
        return n

    def receive(self, discord_id: str, author: str, text: str, from_webhook: bool = False) -> bool:
        """收到 Discord 留言板頻道的訊息。回傳 True 代表新增；False 代表重複或是自己送的。"""
        if from_webhook or not text.strip():
            return False
        try:
            self.store.execute("INSERT INTO messages(time, author, text, source, discord_id) VALUES (?,?,?,'discord',?)",
                               (iso(self.clock.now()), author[:20], text.strip()[:500], str(discord_id)))
        except sqlite3.IntegrityError:
            return False           # 這個編號已經有了：不重複新增
        return True

    def get(self, msg_id: int) -> dict:
        rows = self.store.fetch_all("SELECT * FROM messages WHERE id=?", (msg_id,))
        return rows[0] if rows else {}

    def list(self, limit: int = 50) -> list[dict]:
        return self.store.fetch_all("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (int(limit),))
