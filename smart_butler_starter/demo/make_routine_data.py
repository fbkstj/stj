"""產生 10 天的假作息資料到 demo/routine_demo.db（固定亂數，每次都一樣）：

  9/1～9/8、9/10：正常（約 6:40～7:40 起床，白天持續有活動）
  9/9：異常（10:40 才開始活動，下午幾乎沒有動）

驗證：python -m modules.routine --check --db demo/routine_demo.db --all
預期只有 9/9 被提醒（還沒起床＋下午活動偏少），其他日子沒有提醒。
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.clock import TAIPEI, iso  # noqa: E402
from core.events import Event  # noqa: E402
from core.store import Store  # noqa: E402

DB = Path(__file__).resolve().parent / "routine_demo.db"
ABNORMAL_DAY = 9


def generate(db: Path = DB, abnormal_day: int = ABNORMAL_DAY) -> int:
    """產生假資料到 db，回傳活動筆數。"""
    db = Path(db)
    if db.exists():
        db.unlink()
    store = Store(db)
    rng = random.Random(42)
    n = 0
    for day in range(1, 11):
        base = datetime(2026, 9, day, tzinfo=TAIPEI)
        if day == abnormal_day:
            t = base + timedelta(hours=10, minutes=40)
        else:
            t = base + timedelta(hours=6, minutes=40 + rng.randint(0, 60))
        end = base + timedelta(hours=21)
        while t < end:
            gap = rng.randint(8, 20)
            if day == abnormal_day and 12 <= t.hour < 17:
                gap = rng.randint(90, 120)          # 下午幾乎沒動
            store.save_event(Event("care", "activity", "info", "偵測到活動", time=iso(t)))
            n += 1
            t += timedelta(minutes=gap)
    store.close()
    return n


def main():
    n = generate()
    print(f"已產生 {DB.name}：10 天、{n} 筆活動（第 {ABNORMAL_DAY} 天是異常日）")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    main()
