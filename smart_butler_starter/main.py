"""智慧管家主程式：啟動所有模組、管理介面，並持續監看。

  python main.py --demo              示範模式（示範影片＋模擬資料，不開攝影機、不送 Discord）
  python main.py --demo --duration 120   執行 120 秒後自動結束
  python main.py                     正式模式（依 settings.yaml；攝影機與 Discord 要先經過同意）

執行中可按鍵：F9（可在設定改）＝一鍵求救、q＝結束。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

from core import console
from core.app import App
from core.clock import parse_hhmm
from core.config import ROOT, ConfigError, load_settings
from core.events import Event
from core.health import HealthMonitor, cleanup
from core.supervisor import Supervisor

log = logging.getLogger("main")

F_KEYS = {0x3B + i: f"F{i + 1}" for i in range(10)} | {0x85: "F11", 0x86: "F12"}


def read_key():
    """讀取主程式視窗的按鍵（只在 Windows 終端機有效）；沒有按鍵回傳 None。"""
    try:
        import msvcrt
    except ImportError:
        return None
    if not msvcrt.kbhit():
        return None
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        return F_KEYS.get(ord(msvcrt.getwch()))
    return ch


def start_web(app, supervisor, health):
    try:
        from web.app import create_app
        from werkzeug.serving import make_server
    except ImportError as e:
        log.warning("沒有安裝 Flask，管理介面不啟動（%s）", e)
        return None
    w = app.settings["web"]
    logging.getLogger("werkzeug").setLevel(logging.WARNING)     # 不要每次開網頁都印一行
    server = make_server(w["host"], w["port"], create_app(app, supervisor, health), threaded=True)
    threading.Thread(target=server.serve_forever, name="web", daemon=True).start()
    print(f"管理介面：http://{w['host']}:{w['port']}（只有這台電腦能開）", flush=True)
    return server


def main(argv=None) -> int:
    console.setup()
    p = argparse.ArgumentParser(description="智慧管家主程式")
    p.add_argument("--demo", action="store_true", help="示範模式：用示範影片與模擬資料")
    p.add_argument("--duration", type=float, default=0, help="執行幾秒後自動結束（0＝不結束）")
    p.add_argument("--no-web", action="store_true", help="不啟動管理介面")
    args = p.parse_args(argv)
    os.chdir(ROOT)

    try:
        settings = load_settings(demo=args.demo)
    except ConfigError as e:
        print(e)
        return 1

    app = App(settings, demo=args.demo)
    supervisor = Supervisor(app)
    names = supervisor.load()
    health = HealthMonitor(app)
    mode = "示範模式" if args.demo else "正式模式"
    print(f"=== {settings['system']['name']} 啟動（{mode}），資料放在 {app.data_dir} ===", flush=True)
    if app.privacy:
        print("隱私模式開啟中：不存影像與對話內容", flush=True)
    supervisor.start_all()
    server = None if args.no_web else start_web(app, supervisor, health)
    app.bus.publish(Event("main", "system", "info", f"管家啟動（{mode}），開啟 {len(names)} 個模組"))
    sos_key = settings["sos"]["key"]
    print(f"按 {sos_key} 求救、按 q 結束。", flush=True)

    cleanup(app)
    t0 = time.monotonic()
    next_check = next_health = t0 + 3
    last_cleanup_day = app.clock.now().date()
    try:
        while True:
            time.sleep(0.2)
            now = time.monotonic()
            key = read_key()
            if key == sos_key and app.module("sos"):
                app.module("sos").trigger("鍵盤")
            elif key in ("q", "Q"):
                break
            app.notifier.tick()
            if now >= next_check:
                supervisor.check_modules()
                next_check = now + settings["system"]["module_check_sec"]
            if now >= next_health:
                health.run()
                next_health = now + settings["system"]["health_interval_sec"]
            today = app.clock.now()
            h, m = parse_hhmm(settings["system"]["cleanup_time"])
            if today.date() != last_cleanup_day and (today.hour, today.minute) >= (h, m):
                cleanup(app)
                last_cleanup_day = today.date()
            if args.duration and now - t0 >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    print("正在安全停止所有模組……", flush=True)
    supervisor.stop_all()
    if server:
        server.shutdown()
    app.bus.publish(Event("main", "system", "info", "管家已停止"))
    errors = app.bus.errors
    print(f"已結束。事件總數 {app.store.count()} 筆，訂閱者錯誤 {len(errors)} 筆。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
