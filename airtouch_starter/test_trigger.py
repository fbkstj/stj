"""測試觸發邏輯：不用鏡頭，模擬「每秒 30 格」的手勢序列，檢查蓄力、重複、冷卻、手勢鎖是否照規格運作。

用法：python test_trigger.py
修改 gestures.py 的 GestureTrigger 或 config.json 的時間設定後，都要重跑一次。
"""
import json
import os
import sys

from gestures import GestureTrigger

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30


def simulate(cfg, script, profile="youtube", switch_at=None):
    """script：[(手勢, 秒數), ...]，回傳 [(時間, 動作), ...]。
    switch_at＝(秒數, 模式)：在那個時間切換應用程式模式。"""
    trig = GestureTrigger(cfg, cfg["profiles"][profile]["gestures"])
    t, events = 0.0, []
    for gesture, sec in script:
        for _ in range(int(round(sec * FPS))):
            if switch_at and abs(t - switch_at[0]) < 0.5 / FPS:
                trig.set_map(cfg["profiles"][switch_at[1]]["gestures"])
            _, _, ev = trig.update(gesture, t)
            if ev:
                events.append((round(t, 2), ev["action"]))
            t += 1 / FPS
    return events


def actions(events):
    return [a for _, a in events]


def main():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    ga = cfg["profiles"]["youtube"]["gestures"]
    cases = []

    ev = simulate(cfg, [("no_hand", 0.5), ("open_palm", 2.0), ("no_hand", 0.5)])
    cases.append(("手掌張開維持 2 秒只觸發 1 次", actions(ev) == ["play_pause"]))
    cases.append(("觸發時間約在蓄力時間之後",
                  bool(ev) and 0.5 + ga["open_palm"]["hold_sec"] <= ev[0][0] <= 0.5 + ga["open_palm"]["hold_sec"] + 0.2))

    ev = simulate(cfg, [("no_hand", 0.5), ("open_palm", 0.3), ("no_hand", 0.5)])
    cases.append(("手掌張開太短（0.3 秒）不觸發", actions(ev) == []))

    flicker = []
    for i in range(30):
        flicker.append(("none" if i % 10 == 5 else "open_palm", 1 / FPS))
    ev = simulate(cfg, [("no_hand", 0.5)] + flicker + [("no_hand", 0.5)])
    cases.append(("偶爾一格認錯，不會打斷蓄力", actions(ev) == ["play_pause"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("thumb_up", 1.3), ("no_hand", 0.5)])
    spec = ga["thumb_up"]
    expected = 1 + int((1.3 - spec["hold_sec"] - 0.15) / spec["repeat_sec"])
    cases.append((f"大拇指朝上維持 1.3 秒會重複調音量（約 {expected} 次）",
                  actions(ev).count("volume_up") in (expected - 1, expected, expected + 1)))

    ev = simulate(cfg, [("no_hand", 0.5), ("open_palm", 1.0), ("no_hand", 0.2), ("open_palm", 1.0), ("no_hand", 0.5)])
    cases.append(("放下再比，可以再觸發一次", actions(ev) == ["play_pause", "play_pause"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("fist", 2.0), ("open_palm", 1.5), ("point_right", 1.0), ("no_hand", 0.5)])
    cases.append(("握拳鎖定後，其他手勢都不觸發", actions(ev) == ["lock"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("fist", 2.0), ("no_hand", 0.5), ("fist", 2.0), ("open_palm", 1.0),
                        ("no_hand", 0.5)])
    cases.append(("再握拳一次解鎖，手勢恢復作用", actions(ev) == ["lock", "unlock", "play_pause"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("fist", 1.0), ("no_hand", 0.5)])
    cases.append(("握拳不到鎖定時間不會鎖定", actions(ev) == []))

    ev = simulate(cfg, [("no_hand", 0.5), ("too_far", 2.0), ("none", 2.0), ("no_hand", 0.5)])
    cases.append(("手太遠或沒有指令時不觸發", actions(ev) == []))

    ev = simulate(cfg, [("no_hand", 0.5), ("point_right", 1.0), ("no_hand", 0.5)], profile="powerpoint")
    cases.append(("簡報模式：食指向右＝下一頁", actions(ev) == ["next_page"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("thumb_up", 1.5), ("no_hand", 0.5)], profile="pdf")
    cases.append(("PDF 模式：大拇指朝上＝放大，會重複", actions(ev)[:2] == ["zoom_in", "zoom_in"]))

    ev = simulate(cfg, [("no_hand", 0.5), ("open_palm", 0.8), ("no_hand", 0.5)], profile="teams")
    cases.append(("會議模式：手掌張開要比較久（0.8 秒不觸發）", actions(ev) == []))

    ev = simulate(cfg, [("no_hand", 0.5), ("open_palm", 3.0), ("no_hand", 0.5)], switch_at=(1.3, "powerpoint"))
    cases.append(("切換模式時，手上正在比的手勢不會馬上觸發新模式的動作", actions(ev) == ["play_pause"]))

    passed = 0
    for name, ok in cases:
        passed += ok
        print(("通過  " if ok else "失敗  ") + name)
    print(f"\n通過 {passed}/{len(cases)}")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
