"""在終端機和管家文字對話：python -m modules.chat（輸入 q 離開）。
只啟動對話、用藥、求救三個模組；通報依設定（預設為模擬，不會真的送出）。"""
import os
import sys

from core import console
from core.app import App
from core.config import ROOT, ConfigError, load_settings
from core.supervisor import MODULE_CLASSES, Supervisor


def main():
    console.setup()
    os.chdir(ROOT)
    try:
        settings = load_settings(demo="--demo" in sys.argv)
    except ConfigError as e:
        print(e)
        return 1
    app = App(settings, demo=True)
    sup = Supervisor(app, {k: MODULE_CLASSES[k] for k in ("chat", "meds", "sos")})
    sup.load()
    sup.start_all()
    chat = app.module("chat")
    print("和管家說話（輸入 q 離開）。可以試試：打開客廳燈、客廳暗一點、打開電暖器、我吃藥了、救命")
    while True:
        try:
            text = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("q", "quit", "exit"):
            break
        print("管家：" + chat.handle(text))
    sup.stop_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
