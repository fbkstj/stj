"""L4 模組管理：依設定載入模組、定時檢查、當掉自動重啟。

重啟規則：模組異常就重啟並發「注意」；同一模組 10 分鐘內重啟 3 次以上，
就不再重啟，改發「緊急」，請家人或維護的人來看。
"""
from __future__ import annotations

import importlib
import logging
from collections import deque

from core.config import MODULE_NAMES

log = logging.getLogger("supervisor")

MODULE_CLASSES = {
    "care": "modules.care.module:CareModule",
    "chat": "modules.chat.module:ChatModule",
    "board": "modules.board.module:BoardModule",
    "camera": "modules.camera.module:CameraModule",
    "meds": "modules.meds.module:MedsModule",
    "daily": "modules.daily.module:DailyModule",
    "sos": "modules.sos.module:SosModule",
    "routine": "modules.routine.module:RoutineModule",
}

RESTART_WINDOW_SEC = 600
RESTART_LIMIT = 3


def load_class(path: str):
    mod, cls = path.split(":")
    return getattr(importlib.import_module(mod), cls)


class Supervisor:
    def __init__(self, app, classes: dict | None = None):
        self.app = app
        self.classes = classes or MODULE_CLASSES
        self.restarts: dict[str, deque] = {}
        self.gave_up: set[str] = set()

    def load(self) -> list[str]:
        """依 settings.yaml 的 modules 開關建立模組；關掉的不會載入。"""
        names = []
        for name in self.classes:
            if name in MODULE_NAMES and not self.app.settings["modules"].get(name, False):
                continue
            cls = load_class(self.classes[name]) if isinstance(self.classes[name], str) else self.classes[name]
            self.app.modules[name] = cls(self.app)
            for kind, method in cls.listens.items():
                self.app.bus.subscribe(self._forward(name, method), kinds=[kind])
            names.append(name)
        return names

    def _forward(self, name: str, method: str):
        """事件一律轉給「目前」的模組物件；模組重啟換了新物件，也不會重複處理。"""
        def forward(event):
            module = self.app.modules.get(name)
            if module is not None and module.running:
                getattr(module, method)(event)
        forward.__qualname__ = f"{name}.{method}"
        return forward

    def start_all(self) -> None:
        for name, m in list(self.app.modules.items()):
            try:
                m.start()
                log.info("啟動模組 %s（%s）", name, m.title)
            except Exception as e:
                m.error = f"啟動失敗：{e}"
                log.error("模組 %s 啟動失敗：%s", name, e)

    def stop_all(self) -> None:
        for name, m in reversed(list(self.app.modules.items())):
            m.stop()
            log.info("已停止模組 %s", name)

    def check_modules(self) -> None:
        for name, m in list(self.app.modules.items()):
            if name in self.gave_up:
                continue
            ok, reason = m.health()
            if not ok:
                self._restart(name, reason)

    def _restart(self, name: str, reason: str) -> None:
        now = self.app.clock.monotonic()
        history = self.restarts.setdefault(name, deque())
        while history and now - history[0] > RESTART_WINDOW_SEC:
            history.popleft()
        old = self.app.modules[name]
        if len(history) >= RESTART_LIMIT:
            self.gave_up.add(name)
            old.stop(timeout=1)
            self.app.bus.publish(_event(name, "urgent",
                f"模組「{old.title}」10 分鐘內重啟超過 {RESTART_LIMIT} 次仍異常，已停止重啟，請盡快檢查（{reason}）"))
            return
        history.append(now)
        old.stop(timeout=1)
        new = type(old)(self.app)
        self.app.modules[name] = new
        try:
            new.start()
        except Exception as e:
            new.error = f"啟動失敗：{e}"
        self.app.bus.publish(_event(name, "warn", f"模組「{old.title}」異常（{reason}），已自動重啟"))

    def status(self) -> list[dict]:
        rows = []
        for name in MODULE_NAMES:
            m = self.app.modules.get(name)
            if m is None:
                rows.append({"name": name, "title": _TITLES.get(name, name), "state": "關閉", "reason": "設定中關閉"})
                continue
            ok, reason = m.health()
            state = "停止重啟" if name in self.gave_up else ("正常" if ok else "異常")
            rows.append({"name": name, "title": m.title, "state": state, "reason": reason})
        return rows


_TITLES = {"care": "長照監護", "chat": "AI 對話與家電", "board": "留言板", "camera": "智慧監視器",
           "meds": "用藥提醒", "daily": "每日平安回報", "sos": "一鍵求救", "routine": "作息異常偵測"}


def _event(source, level, message):
    from core.events import Event
    return Event(source, "module_health", level, message)
