"""測試應用程式模式：不用鏡頭、不會按鍵（模擬模式），檢查
  1. 視窗標題能不能判斷成正確的模式
  2. 每個動作在各模式是否支援、語音意圖有沒有換成正確的動作
  3. config.json 裡每個模式的手勢，都是那個模式支援的動作；快捷鍵名稱都正確

用法：python test_profiles.py
新增或修改模式後一定要重跑；也可以把自己電腦上的視窗標題加進 TITLES 測試。
"""
import json
import os
import sys

import voice_commands
from actions import Actions, match_profile

HERE = os.path.dirname(os.path.abspath(__file__))

TITLES = [
    ("稻香 - YouTube - Google Chrome", "youtube"),
    ("How to use Google Meet - YouTube - Google Chrome", "youtube"),
    ("PowerPoint 投影片放映 - [期末報告.pptx]", "powerpoint"),
    ("期末報告.pptx - PowerPoint", "powerpoint"),
    ("YouTube 教學簡報.pptx - PowerPoint", "powerpoint"),
    ("講義.pdf 和其他 2 個頁面 - 個人 - Microsoft Edge", "pdf"),
    ("講義.pdf - Adobe Acrobat Reader (64-bit)", "pdf"),
    ("Meet - abc-defg-hij - Google Chrome", "meet"),
    ("專題討論 | Microsoft Teams", "teams"),
    ("Zoom Meeting", "zoom"),
    ("Zoom 會議", "zoom"),
    ("未命名 - 記事本", None),
    ("AirTouch", None),
    ("", None),
]

# (模式, 意圖, 預期的實際動作, 是否支援)
ROUTES = [
    ("powerpoint", "next_page", "next_page", True),
    ("youtube", "next_page", "next_page", False),
    ("youtube", "seek_forward", "seek_forward", True),
    ("powerpoint", "seek_forward", "seek_forward", False),
    ("pdf", "zoom_in", "zoom_in", True),
    ("pdf", "goto_page", "goto_page", False),
    ("powerpoint", "goto_page", "goto_page", True),
    ("powerpoint", "goto_title", "goto_title", True),
    ("youtube", "skip_ad", "skip_ad", True),
    ("powerpoint", "skip_ad", "skip_ad", False),
    ("teams", "mute", "mic_toggle", True),
    ("zoom", "mute", "mic_toggle", True),
    ("teams", "system_mute", "mute", True),
    ("youtube", "mute", "mute", True),
    ("meet", "camera_toggle", "camera_toggle", True),
    ("youtube", "mic_toggle", "mic_toggle", False),
    ("pdf", "volume_up", "volume_up", True),
    ("zoom", "play_song", "play_song", True),
    ("pdf", "switch_profile", "switch_profile", True),
]

# (模式, 說的話, 預期的實際動作)
VOICE = [
    ("teams", "靜音", "mic_toggle"),
    ("teams", "電腦靜音", "mute"),
    ("powerpoint", "跳到第三頁", "goto_page"),
    ("powerpoint", "黑畫面", "black_screen"),
    ("pdf", "放大", "zoom_in"),
    ("youtube", "下一頁", "next_page"),
]


def main():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    act = Actions(cfg, dry_run=True)
    results = []

    for title, expected in TITLES:
        got = match_profile(cfg["profiles"], title)
        results.append((f"視窗「{title or '（空白）'}」→ {expected}", got == expected, got))

    for profile, intent, real, supported in ROUTES:
        got_real, got_sup = act.resolve(intent, profile)
        ok, msg, _ = act.run(intent, 3 if intent == "goto_page" else None, profile)
        good = got_real == real and got_sup == supported and ok == supported
        results.append((f"{profile}：{intent} → {real}（{'支援' if supported else '不支援'}）", good, msg))

    for profile, text, real in VOICE:
        cmd = voice_commands.parse(text)
        got = act.resolve(cmd["action"], profile)[0] if cmd else None
        results.append((f"{profile} 模式說「{text}」→ {real}", got == real, got))

    try:
        import pyautogui
        valid_keys = set(pyautogui.KEYBOARD_KEYS)
    except ImportError:
        valid_keys = None
    for name, p in cfg["profiles"].items():
        for gesture, spec in p["gestures"].items():
            sup = act.resolve(spec["action"], name)[1]
            results.append((f"{name}：手勢 {gesture} 的動作 {spec['action']} 有支援", sup, ""))
        if valid_keys is not None:
            bad = [k for keys in p["keys"].values() for k in keys if k not in valid_keys]
            results.append((f"{name}：快捷鍵名稱都正確", not bad, bad))

    passed = 0
    for name, ok, detail in results:
        passed += ok
        print(("通過  " if ok else "失敗  ") + name + ("" if ok else f"   （實際：{detail}）"))
    if valid_keys is None:
        print("（沒有安裝 pyautogui，略過快捷鍵名稱檢查）")
    print(f"\n通過 {passed}/{len(results)}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
