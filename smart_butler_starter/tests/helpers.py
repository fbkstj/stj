"""測試共用：建立一個「假的」系統環境（暫存資料夾、快轉時鐘、不連網的 Discord）。"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.app import App  # noqa: E402
from core.clock import TAIPEI, FakeClock  # noqa: E402
from core.config import deep_merge, load_settings  # noqa: E402
from core.notify import DryRunTransport  # noqa: E402

BASE_SETTINGS = load_settings(ROOT / "config" / "settings.yaml")


def make_settings(tmp: Path, **overrides) -> dict:
    s = copy.deepcopy(BASE_SETTINGS)
    s["system"]["data_dir"] = str(tmp / "data")
    s["system"]["voice"] = False
    return deep_merge(s, overrides)


def make_app(tmp: Path, start=None, transport=None, **overrides) -> App:
    clock = FakeClock(start or datetime(2026, 9, 1, 8, 0, tzinfo=TAIPEI))
    return App(make_settings(tmp, **overrides), demo=False, clock=clock,
               transport=transport or DryRunTransport(echo=False))


class TempDir:
    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="butler_test_"))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


def ensure_demo_media() -> None:
    """測試需要示範影片；沒有的話先產生。"""
    if not (ROOT / "demo" / "care_demo.mp4").exists() or not (ROOT / "demo" / "door_demo.mp4").exists():
        subprocess.run([sys.executable, str(ROOT / "demo" / "make_demo_media.py")], check=True, cwd=ROOT)


class FailingTransport:
    """模擬斷網：送出一律失敗；把 online 改成 True 就恢復。"""

    def __init__(self):
        self.online = False
        self.sent = []

    def send(self, channel, text, attachment=None, mention_everyone=False):
        if not self.online:
            raise ConnectionError("模擬斷網")
        self.sent.append({"channel": channel, "text": text, "attachment": attachment})
        return f"ok-{len(self.sent)}"
