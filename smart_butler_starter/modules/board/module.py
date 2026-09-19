"""L7 留言板模組。

讀取 Discord 留言有兩種來源：
- 示範模式：demo/discord_inbox.jsonl（模擬家人在 Discord 留言，第 3 筆故意和第 1 筆重複）
- 正式模式：.env 有 DISCORD_BOT_TOKEN、settings.yaml 有 discord.board_channel_id 時，
  用 Bot 每 10 秒讀一次頻道的新訊息（Bot 要開啟 Message Content Intent）。

在留言板頻道輸入「已處理 12」，等於在管理介面把第 12 號緊急通報按「已處理」。
"""
from __future__ import annotations

import json
import re

from core.config import get_secret
from core.module import Module
from modules.board.board import Board

API = "https://discord.com/api/v10"


class DemoInbox:
    def __init__(self, path, clock):
        self.items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] \
            if path.exists() else []
        self.clock = clock
        self.t0 = clock.monotonic()
        self.pos = 0

    def fetch(self):
        out = []
        while self.pos < len(self.items) and self.clock.monotonic() - self.t0 >= self.items[self.pos]["at_sec"]:
            it = self.items[self.pos]
            out.append((it["id"], it["author"], it["text"], False))
            self.pos += 1
        return out


class BotInbox:
    """用 Discord REST API 讀取頻道新訊息（只需要 requests，不需要 discord.py）。尚未實機測試。"""

    def __init__(self, token, channel_id, timeout=5):
        self.headers = {"Authorization": f"Bot {token}"}
        self.channel_id = channel_id
        self.timeout = timeout
        self.after = None

    def fetch(self):
        import requests
        params = {"limit": 50}
        if self.after:
            params["after"] = self.after
        r = requests.get(f"{API}/channels/{self.channel_id}/messages", headers=self.headers,
                         params=params, timeout=self.timeout)
        r.raise_for_status()
        msgs = sorted(r.json(), key=lambda m: int(m["id"]))
        if msgs:
            self.after = msgs[-1]["id"]
        return [(m["id"], m["author"].get("global_name") or m["author"]["username"], m.get("content", ""),
                 bool(m.get("webhook_id")) or m["author"].get("bot", False)) for m in msgs]


class BoardModule(Module):
    name = "board"
    title = "留言板"
    interval = 1.0

    def setup(self):
        d = self.settings["discord"]
        notifier = self.app.notifier
        self.board = Board(self.app.store, self.clock, send=self._send, channel=d["channels"]["board"])
        token, channel_id = get_secret("DISCORD_BOT_TOKEN"), str(d.get("board_channel_id") or "")
        if self.app.demo:
            self.inbox = DemoInbox(self.app.root / "demo" / "discord_inbox.jsonl", self.clock)
            self.poll_every = 1
        elif token and channel_id and not d["dry_run"]:
            self.inbox = BotInbox(token, channel_id, d["timeout_sec"])
            self.poll_every = 10
        else:
            self.inbox = None
            self.poll_every = 10
        self._next_poll = 0
        self.last_error = None
        self._notifier = notifier

    def _send(self, channel, text):
        return self._notifier.transport.send(channel, text)

    # 給管理介面用
    def post(self, author, text):
        return self.board.post(author, text)

    def list(self, limit=50):
        return self.board.list(limit)

    def step(self):
        now = self.clock.monotonic()
        if now < self._next_poll:
            return
        self._next_poll = now + self.poll_every
        self.board.sync_pending()
        if not self.inbox:
            return
        try:
            items = self.inbox.fetch()
            self.last_error = None
        except Exception as e:
            self.last_error = f"讀取 Discord 失敗：{type(e).__name__}"
            return
        for did, author, text, from_bot in items:
            m = re.fullmatch(r"\s*已處理\s*#?(\d+)\s*", text or "")
            if m and not from_bot:
                self.app.notifier.ack(int(m[1]), by=f"{author}（Discord）")
                continue
            if self.board.receive(did, author, text, from_bot):
                self.publish("board", "info", f"Discord 新留言（{author}）：{text[:30]}")

    def check(self):
        return (self.last_error is None), (self.last_error or "正常")
