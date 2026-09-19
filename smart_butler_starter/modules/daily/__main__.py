"""立刻產生每日平安回報（測試用）：
  python -m modules.daily --now            今天到目前為止（依設定送出，預設是模擬）
  python -m modules.daily --now --demo     用示範模式的資料（data/demo）
  python -m modules.daily --date 2026-09-09 --db demo/routine_demo.db --print-only
"""
import argparse
import os
import sys
from datetime import date

from core import console
from core.app import App
from core.config import ROOT, ConfigError, load_settings
from core.store import Store
from modules.daily.summary import collect, format_summary


def main():
    console.setup()
    os.chdir(ROOT)
    p = argparse.ArgumentParser(description="立刻產生每日平安回報")
    p.add_argument("--now", action="store_true", help="今天到目前為止")
    p.add_argument("--date", help="指定日期 YYYY-MM-DD")
    p.add_argument("--demo", action="store_true", help="使用示範模式的資料夾")
    p.add_argument("--db", help="改用其他資料庫檔案")
    p.add_argument("--print-only", action="store_true", help="只印出，不送 Discord")
    a = p.parse_args()
    try:
        settings = load_settings(demo=a.demo)
    except ConfigError as e:
        print(e)
        return 1
    day = date.fromisoformat(a.date) if a.date else None
    store = Store(a.db) if a.db else None
    if a.print_only or a.db:
        store = store or App(settings, echo=False).store
        s = collect(store, day or date.today(), None, settings["routine"]["activity_kinds"])
        print(format_summary(s))
        return 0
    app = App(settings, demo=a.demo)
    from modules.daily.module import DailyModule
    mod = DailyModule(app)
    mod.setup()
    now = app.clock.now()
    text = mod.send_summary(day or now.date(), now if not day else None)
    print("----- 摘要內容 -----")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
