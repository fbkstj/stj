"""L3 Discord 通報器：所有通報都經過這裡。

- 依等級決定格式：資訊（一般）、注意（⚠️）、緊急（🚨＋@everyone＋截圖）
- 緊急通報沒人按「已處理」，每 N 分鐘重送，最多 M 次（設定在 settings.yaml）
- 送不出去（斷網）先存進 data/outbox，恢復後依時間順序補送，並標示「延遲送達」
- 練習時 discord.dry_run: true：不真的送出，只寫進 data/discord_dryrun.log

測試：python -m core.notify --test   依序送出三種等級的測試訊息
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

from core.clock import Clock, iso, parse_iso
from core.events import LEVEL_NAMES, LEVELS, Event

log = logging.getLogger("notify")

ALERT_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    time TEXT NOT NULL,
    message TEXT NOT NULL,
    attachment TEXT,
    sent_count INTEGER NOT NULL DEFAULT 1,
    last_sent TEXT NOT NULL,
    acked_at TEXT,
    acked_by TEXT
);
"""


class SendError(Exception):
    pass


# ---------- 送出方式 ----------
class DryRunTransport:
    """練習模式：不連網，只記錄「本來要送出的內容」。"""

    def __init__(self, log_path: Path | None = None, echo: bool = True):
        self.log_path = log_path
        self.echo = echo
        self.sent: list[dict] = []
        self._n = 0

    def send(self, channel: str, text: str, attachment: str | None = None, mention_everyone=False) -> str:
        self._n += 1
        item = {"channel": channel, "text": text, "attachment": attachment}
        self.sent.append(item)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        if self.echo:
            extra = f"（附件 {Path(attachment).name}）" if attachment else ""
            print(f"[Discord 模擬 #{channel}] {text}{extra}", flush=True)
        return f"dry-{time.time_ns()}-{self._n}"   # 每次都不一樣，重新啟動也不會重複


class WebhookTransport:
    """用 Webhook 送出（只能送、不能讀）。網址從 .env 讀取，不會出現在程式或畫面上。"""

    def __init__(self, urls: dict[str, str], timeout: float = 5):
        self.urls = urls           # {"測試通報": "https://discord.com/api/webhooks/..."}
        self.timeout = timeout

    def send(self, channel: str, text: str, attachment: str | None = None, mention_everyone=False) -> str:
        import requests
        url = self.urls.get(channel)
        if not url:
            raise SendError(f"頻道「{channel}」沒有設定 Webhook（請檢查 .env）")
        payload = {"content": text[:1990],
                   "allowed_mentions": {"parse": ["everyone"] if mention_everyone else []}}
        try:
            if attachment and Path(attachment).exists():
                with open(attachment, "rb") as f:
                    r = requests.post(url, params={"wait": "true"}, timeout=self.timeout,
                                      data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                                      files={"files[0]": (Path(attachment).name, f, "image/jpeg")})
            else:
                r = requests.post(url, params={"wait": "true"}, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            raise SendError(f"連不上 Discord：{type(e).__name__}") from None
        if r.status_code >= 300:
            raise SendError(f"Discord 回應 {r.status_code}")
        try:
            return str(r.json().get("id", ""))
        except ValueError:
            return ""


def make_transport(settings: dict, data_dir: Path, echo: bool = True):
    """依設定選擇送出方式：dry_run 或沒有 Webhook → 模擬；否則用 Webhook。"""
    from core.config import get_secret
    d = settings["discord"]
    urls = {}
    for key, env in (("notify", "DISCORD_WEBHOOK_TEST"), ("board", "DISCORD_WEBHOOK_BOARD")):
        if get_secret(env):
            urls[d["channels"][key]] = get_secret(env)
    if d["dry_run"] or not urls:
        return DryRunTransport(Path(data_dir) / "discord_dryrun.log", echo=echo)
    return WebhookTransport(urls, timeout=d["timeout_sec"])


# ---------- 通報器 ----------
SOURCE_NAMES = {"care": "長照監護", "chat": "對話", "board": "留言板", "camera": "監視器", "meds": "用藥",
                "daily": "平安回報", "sos": "求救", "routine": "作息", "health": "健康檢查", "main": "主程式",
                "notify": "通報測試"}


def format_message(event: Event, system_name: str = "智慧管家") -> str:
    hhmm = event.time[11:16] if event.time else ""
    body = f"{event.message}（{hhmm}，{SOURCE_NAMES.get(event.source, event.source)}）"
    if event.level == "urgent":
        return f"🚨 緊急｜@everyone {body}"
    if event.level == "warn":
        return f"⚠️ 注意｜{body}"
    return f"ℹ️ {body}"


class Notifier:
    def __init__(self, settings: dict, store, transport, clock: Clock | None = None, data_dir: Path | None = None):
        self.settings = settings
        self.store = store
        self.transport = transport
        self.clock = clock or Clock()
        self.outbox = Path(data_dir or "data") / "outbox"
        self.outbox.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._seq = 0
        self.online = True           # 最近一次送出是否成功
        self.last_latency_ms = None  # 最近一次送出花的時間
        self.retry_sec = 30          # 補送失敗後，隔幾秒再試
        self._next_flush = 0.0
        store.executescript(ALERT_SCHEMA)

    @property
    def channel(self) -> str:
        return self.settings["discord"]["channels"]["notify"]

    # EventBus 訂閱者
    def handle(self, event: Event) -> None:
        d = self.settings["discord"]
        if event.kind in (d.get("skip_kinds") or []):
            return
        if LEVELS.index(event.level) < LEVELS.index(d["min_level"]):
            return
        text = format_message(event, self.settings["system"]["name"])
        attachment = event.attachment if event.level != "info" else None
        self.deliver(text, attachment, mention=event.level == "urgent", time_text=event.time)
        if event.level == "urgent":
            self.store.execute(
                "INSERT INTO alerts(event_id, time, message, attachment, sent_count, last_sent) VALUES (?,?,?,?,1,?)",
                (event.id, event.time, event.message, event.attachment, iso(self.clock.now())))

    def deliver(self, text: str, attachment=None, mention=False, time_text=None, channel=None) -> bool:
        """送出一則訊息；失敗就放進 outbox。回傳是否成功送出。"""
        channel = channel or self.channel
        start = self.clock.monotonic()
        try:
            self.transport.send(channel, text, attachment, mention)
            self.online = True
            self.last_latency_ms = round((self.clock.monotonic() - start) * 1000)
            return True
        except Exception as e:
            self.online = False
            log.warning("送出失敗，先存進待補送佇列：%s", e)
            self._queue(channel, text, attachment, mention, time_text or iso(self.clock.now()))
            return False

    def _queue(self, channel, text, attachment, mention, time_text) -> None:
        with self._lock:
            self._seq += 1
            stamp = self.clock.now().strftime("%Y%m%d_%H%M%S")
            path = self.outbox / f"{stamp}_{self._seq:04d}.json"
            path.write_text(json.dumps({"channel": channel, "text": text, "attachment": attachment,
                                        "mention": mention, "time": time_text}, ensure_ascii=False),
                            encoding="utf-8")

    def pending_count(self) -> int:
        return len(list(self.outbox.glob("*.json")))

    def flush_outbox(self) -> int:
        """依時間順序補送；遇到失敗就停（下次再試）。回傳補送成功的數量。"""
        sent = 0
        with self._lock:
            for path in sorted(self.outbox.glob("*.json")):
                item = json.loads(path.read_text(encoding="utf-8"))
                hhmm = item["time"][11:16] if item.get("time") else ""
                text = f"{item['text']}（延遲送達，原時間 {hhmm}）"
                try:
                    self.transport.send(item["channel"], text, item.get("attachment"), item.get("mention", False))
                except Exception as e:
                    self.online = False
                    log.info("補送仍失敗，稍後再試：%s", e)
                    break
                path.unlink()
                sent += 1
                self.online = True
        return sent

    # ---- 緊急通報的重送與確認 ----
    def open_alerts(self) -> list[dict]:
        return self.store.fetch_all("SELECT * FROM alerts WHERE acked_at IS NULL ORDER BY id")

    def ack(self, alert_id: int, by: str = "管理介面") -> bool:
        cur = self.store.execute("UPDATE alerts SET acked_at=?, acked_by=? WHERE id=? AND acked_at IS NULL",
                                 (iso(self.clock.now()), by, alert_id))
        if cur.rowcount:
            self.deliver(f"✅ 緊急通報 #{alert_id} 已由 {by} 處理")
        return cur.rowcount > 0

    def tick(self) -> None:
        """主程式每幾秒呼叫一次：重送沒人處理的緊急通報、補送 outbox。"""
        d = self.settings["discord"]
        now = self.clock.now()
        for a in self.open_alerts():
            if a["sent_count"] >= d["urgent_repeat_max"]:
                continue
            if (now - parse_iso(a["last_sent"])).total_seconds() >= d["urgent_repeat_min"] * 60:
                n = a["sent_count"] + 1
                text = (f"🚨 緊急（第 {n} 次提醒，尚未有人處理）｜@everyone {a['message']}"
                        f"（處理後請到管理介面按「已處理」#{a['id']}）")
                self.deliver(text, a["attachment"], mention=True, time_text=a["time"])
                self.store.execute("UPDATE alerts SET sent_count=?, last_sent=? WHERE id=?", (n, iso(now), a["id"]))
        if self.pending_count() and self.clock.monotonic() >= self._next_flush:
            self.flush_outbox()
            self._next_flush = self.clock.monotonic() + (0 if self.online else self.retry_sec)


def _cli() -> None:
    from core import console
    from core.config import ConfigError, data_dir, get_settings
    from core.events import EventBus
    from core.store import Store
    console.setup()
    if "--test" not in sys.argv:
        print("用法：python -m core.notify --test")
        return
    try:
        settings = get_settings(demo="--demo" in sys.argv)
    except ConfigError as e:
        print(e)
        sys.exit(1)
    ddir = data_dir(settings)
    transport = make_transport(settings, ddir)
    mode = "模擬（dry_run，不會真的送出）" if isinstance(transport, DryRunTransport) else "Webhook 送到測試頻道"
    print(f"送出方式：{mode}")
    store = Store(ddir / "aina.db")
    bus = EventBus()
    bus.subscribe(store.save_event)
    notifier = Notifier(settings, store, transport, data_dir=ddir)
    bus.subscribe(notifier.handle)
    for level in LEVELS:
        bus.publish(Event("notify", "test", level, f"這是一則「{LEVEL_NAMES[level]}」等級的測試訊息"))
    print(f"完成：送出 {3 - notifier.pending_count()} 則；待補送 {notifier.pending_count()} 則。")
    print("緊急測試訊息已登記，不需要處理時請到管理介面按「已處理」，否則會依設定重送。")


if __name__ == "__main__":
    _cli()
