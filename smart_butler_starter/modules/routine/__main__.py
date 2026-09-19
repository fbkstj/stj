"""立即檢查作息（測試用），只印出結果、不送通報：
  python -m modules.routine --check                              用目前的資料庫檢查現在
  python -m modules.routine --check --db demo/routine_demo.db --all   逐日檢查假資料（每天 21:00）
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

from core import console
from core.clock import TAIPEI, Clock
from core.config import ROOT, ConfigError, data_dir, load_settings
from core.store import Store
from modules.routine.analyzer import check


def main():
    console.setup()
    os.chdir(ROOT)
    p = argparse.ArgumentParser(description="作息異常檢查")
    p.add_argument("--check", action="store_true")
    p.add_argument("--db", help="資料庫檔案（預設 data/aina.db）")
    p.add_argument("--at", help="假裝現在是這個時間，例如 \"2026-09-09 10:30\"")
    p.add_argument("--all", action="store_true", help="資料庫裡每一天都在 21:00 檢查一次")
    p.add_argument("--tolerance", type=float, help="暫時改用這個容許分鐘數（不改設定檔）")
    p.add_argument("--demo", action="store_true")
    a = p.parse_args()
    try:
        settings = load_settings(demo=a.demo)
    except ConfigError as e:
        print(e)
        return 1
    cfg = dict(settings["routine"])
    if a.tolerance is not None:
        cfg["wake_tolerance_min"] = a.tolerance
    store = Store(a.db or data_dir(settings) / "aina.db")
    if a.all:
        rows = store.query(kind=cfg["activity_kinds"])
        if not rows:
            print("資料庫沒有活動紀錄。先執行 python demo/make_routine_data.py")
            return 1
        first = datetime.fromisoformat(rows[0]["time"]).date()
        last = datetime.fromisoformat(rows[-1]["time"]).date()
        d, total = first, 0
        while d <= last:
            for hhmm in ("10:30", "21:00"):
                h, m = map(int, hhmm.split(":"))
                now = datetime(d.year, d.month, d.day, h, m, tzinfo=TAIPEI)
                alerts, note = check(store, now, cfg)
                if hhmm == "21:00" or alerts:
                    shown = "；".join(msg for _, msg in alerts) if alerts else ("正常" if "不足" not in note else note)
                    print(f"{d}（{hhmm}）：{shown}")
                    total += len(alerts)
            d += timedelta(days=1)
        print(f"合計提醒 {total} 次。判斷基準：{note}")
        return 0
    now = datetime.fromisoformat(a.at).replace(tzinfo=TAIPEI) if a.at else Clock().now()
    alerts, note = check(store, now, cfg)
    print(note)
    for _, msg in alerts:
        print("  ⚠️ " + msg)
    if not alerts:
        print("  沒有異常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
