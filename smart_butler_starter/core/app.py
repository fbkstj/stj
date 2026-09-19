"""把共用服務組在一起：設定、時鐘、事件匯流排、紀錄、通報器、各模組。

每個模組都拿到同一個 App 物件（self.app），透過它發布事件、查資料庫、找其他模組。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from core.clock import Clock
from core.config import ROOT, data_dir
from core.events import EventBus
from core.notify import Notifier, make_transport
from core.store import Store


class App:
    def __init__(self, settings: dict, demo: bool = False, clock: Clock | None = None,
                 transport=None, store: Store | None = None, echo: bool = True):
        self.settings = settings
        self.demo = demo
        self.clock = clock or Clock()
        self.root = ROOT
        self.data_dir = data_dir(settings)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir = self.data_dir / "snapshots"
        self.bus = EventBus(self.clock)
        self.store = store or Store(self.data_dir / "aina.db")
        self.bus.subscribe(self.store.save_event)          # 1. 先存檔（填入事件編號）
        self.transport = transport or make_transport(settings, self.data_dir, echo=echo)
        self.notifier = Notifier(settings, self.store, self.transport, self.clock, self.data_dir)
        self.bus.subscribe(self.notifier.handle)            # 2. 再通報
        self.modules: dict = {}                              # 名稱 → 模組（由主程式填入）

    @property
    def privacy(self) -> bool:
        return bool(self.settings["system"]["privacy_mode"])

    def module(self, name: str):
        return self.modules.get(name)

    def resolve(self, path: str | Path) -> Path:
        """設定檔裡的相對路徑，一律以專案資料夾為起點。"""
        p = Path(path)
        return p if p.is_absolute() else self.root / p

    def say(self, text: str) -> None:
        """提醒長輩：一定印在畫面上；system.voice 為 true 時再用 Windows 內建語音念出來。"""
        print(f"【管家說】{text}", flush=True)
        if self.settings["system"].get("voice"):
            script = ("Add-Type -AssemblyName System.Speech; "
                      "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                      "$s.Speak([Console]::In.ReadToEnd())")
            try:
                subprocess.Popen(["powershell", "-NoProfile", "-Command", script], stdin=subprocess.PIPE,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).communicate(
                    text.encode("utf-8"), timeout=30)
            except Exception:
                pass
