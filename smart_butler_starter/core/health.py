"""L14 系統穩定：健康檢查與自動清除過期資料。

健康檢查（每 health_interval_sec 秒）：攝影機、網路、硬碟空間、待補送訊息。
某一項「變成異常」發「注意」，「恢復正常」發「資訊」；狀態沒變就不重複通報。
"""
from __future__ import annotations

import shutil
import socket
from datetime import timedelta

from core.clock import iso
from core.events import Event


def check_network(host: str = "discord.com", port: int = 443, timeout: float = 3) -> tuple[bool, str]:
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True, "可以連到 Discord"
    except OSError:
        return False, "連不上網路（通報會先存起來，恢復後補送）"


def check_disk(path, min_free_gb: float) -> tuple[bool, str]:
    free = shutil.disk_usage(path).free / 1024 ** 3
    return (free >= min_free_gb), f"剩餘 {free:.1f} GB"


class HealthMonitor:
    def __init__(self, app, net_check=check_network, disk_check=check_disk):
        self.app = app
        self.net_check = net_check
        self.disk_check = disk_check
        self.state: dict[str, bool] = {}
        self.last: dict[str, tuple[bool, str]] = {}

    def collect(self) -> dict[str, tuple[bool, str]]:
        s = self.app.settings["system"]
        items = {"網路": self.net_check(), "硬碟": self.disk_check(self.app.data_dir, s["min_free_gb"])}
        for name, label in (("care", "攝影機（長照）"), ("camera", "攝影機（門口）")):
            m = self.app.modules.get(name)
            if m is not None:
                items[label] = m.check()
        pending = self.app.notifier.pending_count()
        items["待補送通報"] = (pending == 0, f"{pending} 則")
        return items

    def run(self) -> dict[str, tuple[bool, str]]:
        items = self.collect()
        for name, (ok, msg) in items.items():
            before = self.state.get(name, True)
            if before and not ok:
                self.app.bus.publish(Event("health", "health", "warn", f"健康檢查：{name}異常（{msg}）"))
            elif not before and ok:
                self.app.bus.publish(Event("health", "health", "info", f"健康檢查：{name}已恢復正常（{msg}）"))
            self.state[name] = ok
        self.last = items
        return items


def cleanup(app) -> dict[str, int]:
    """依保存天數刪除過期資料：截圖、對話紀錄；keep_events 為 false 時也刪事件。"""
    s = app.settings["system"]
    cutoff = app.clock.now() - timedelta(days=s["retention_days"])
    removed = {"截圖": 0, "對話紀錄": 0, "事件": 0}
    if app.snapshot_dir.exists():
        for p in app.snapshot_dir.glob("*.jpg"):
            if p.stat().st_mtime < cutoff.timestamp():
                p.unlink()
                removed["截圖"] += 1
    removed["對話紀錄"] = app.store.delete_events_before(cutoff, kinds=["chat"])
    if not s["keep_events"]:
        removed["事件"] = app.store.delete_events_before(cutoff)
    if any(removed.values()):
        app.bus.publish(Event("health", "cleanup", "info",
                              "已清除過期資料：" + "、".join(f"{k} {v} 筆" for k, v in removed.items()),
                              data={"cutoff": iso(cutoff)}))
    return removed
