"""時間：全系統統一用台北時間（UTC+8）。測試時換成 FakeClock，就能「快轉」時間。"""
from datetime import datetime, timedelta, timezone
import time

TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")


class Clock:
    """真實時間。"""

    def now(self) -> datetime:
        return datetime.now(TAIPEI)

    def monotonic(self) -> float:
        return time.monotonic()


class FakeClock(Clock):
    """測試用時鐘：時間不會自己走，要呼叫 advance() 才前進。"""

    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 9, 1, 8, 0, tzinfo=TAIPEI)
        if self._now.tzinfo is None:
            self._now = self._now.replace(tzinfo=TAIPEI)
        self._mono = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, seconds: float = 0, minutes: float = 0) -> None:
        delta = seconds + minutes * 60
        self._now += timedelta(seconds=delta)
        self._mono += delta

    def set(self, when: datetime) -> None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=TAIPEI)
        self._mono += (when - self._now).total_seconds()
        self._now = when


def iso(dt: datetime) -> str:
    """存進資料庫的時間格式，例如 2026-09-01T08:00:00+08:00（字串可以直接比大小）。"""
    return dt.astimezone(TAIPEI).isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(TAIPEI)


def parse_hhmm(text: str) -> tuple[int, int]:
    h, m = str(text).split(":")
    return int(h), int(m)
