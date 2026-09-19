"""不需要硬體的測試：檢查語音規則（voice.Announcer）與傳給 ESP32 的狀態格式。

用法：python test_voice_logic.py
全部通過會顯示「通過 N/N」。改了 voice.py 的規則後，請同步修改這裡的預期結果。
"""
from voice import (CLIP_BIG, CLIP_CAR, CLIP_DANGER, CLIP_DANGER_BIG, CLIP_DANGER_CAR,
                   CLIP_DANGER_MOTORCYCLE, CLIP_MOTORCYCLE, CLIP_MULTI, Announcer, status_line)


def esp32_parse(line):
    """模擬 esp32_rear_alert.ino 的 handleLine，確認 ESP32 看得懂。"""
    if len(line) > 8:
        return None
    if len(line) == 5 and line[0] == "S" and line[1] in "012" and line[3:].isdigit():
        return int(line[1]), line[2], int(line[3:])
    return None


def run_announcer(steps, cooldown=1.5):
    """steps：[(時間, 警示中的車, 整體等級, 事件), ...]，回傳每一步的語音編號（沒說話為 None）。"""
    a = Announcer(cooldown=cooldown)
    return [(r[0] if r else None) for r in (a.update(*s) for s in steps)]


CASES = [
    ("單台機車進入注意", [(0.0, [(1, "motorcycle", 1)], 1, "alert_on")], [CLIP_MOTORCYCLE]),
    ("單台汽車進入注意", [(0.0, [(1, "car", 1)], 1, "alert_on")], [CLIP_CAR]),
    ("貨車算大型車", [(0.0, [(1, "truck", 1)], 1, "alert_on")], [CLIP_BIG]),
    ("公車算大型車", [(0.0, [(1, "bus", 1)], 1, "alert_on")], [CLIP_BIG]),
    ("同一台車只說一次",
     [(0.0, [(1, "car", 1)], 1, "alert_on"), (2.0, [(1, "car", 1)], 1, None), (4.0, [(1, "car", 1)], 1, None)],
     [CLIP_CAR, None, None]),
    ("兩台新車同時出現說多台車", [(0.0, [(1, "car", 1), (2, "motorcycle", 1)], 1, "alert_on")], [CLIP_MULTI]),
    ("多台車中有大型車優先說大型車", [(0.0, [(1, "car", 1), (2, "truck", 1)], 1, "alert_on")], [CLIP_BIG]),
    ("冷卻時間內的新車延後再說",
     [(0.0, [(1, "car", 1)], 1, "alert_on"), (0.5, [(1, "car", 1), (2, "motorcycle", 1)], 1, None),
      (1.6, [(1, "car", 1), (2, "motorcycle", 1)], 1, None)],
     [CLIP_CAR, None, CLIP_MOTORCYCLE]),
    ("升到危險立刻說危險＋車種",
     [(0.0, [(1, "car", 1)], 1, "alert_on"), (0.3, [(1, "car", 2)], 2, "escalate")],
     [CLIP_CAR, CLIP_DANGER_CAR]),
    ("直接進入危險說危險＋車種，之後不再重複",
     [(0.0, [(1, "motorcycle", 2)], 2, "alert_on"), (2.0, [(1, "motorcycle", 2)], 2, None)],
     [CLIP_DANGER_MOTORCYCLE, None]),
    ("危險的是大型車",
     [(0.0, [(1, "truck", 2)], 2, "alert_on")], [CLIP_DANGER_BIG]),
    ("兩種車同時危險說危險，注意",
     [(0.0, [(1, "car", 2), (2, "motorcycle", 2)], 2, "alert_on")], [CLIP_DANGER]),
    ("只有一台危險、另一台注意時說危險的那台",
     [(0.0, [(1, "car", 1), (2, "bus", 2)], 2, "alert_on")], [CLIP_DANGER_BIG]),
    ("同一次警示只說一次危險",
     [(0.0, [(1, "car", 2)], 2, "alert_on"), (0.5, [(1, "car", 2)], 2, None), (3.0, [(1, "car", 2)], 2, None)],
     [CLIP_DANGER_CAR, None, None]),
    ("解除後下一次警示可以再說危險",
     [(0.0, [(1, "car", 2)], 2, "alert_on"), (2.0, [], 0, "alert_off"), (5.0, [(2, "car", 2)], 2, "alert_on")],
     [CLIP_DANGER_CAR, None, CLIP_DANGER_CAR]),
    ("沒有警示中的車就不說話", [(0.0, [], 0, None)], [None]),
]

STATUS = [
    ((0, "", None), "S0N00"),
    ((1, "truck", 2.46), "S1B25"),
    ((1, "bus", 3.0), "S1B30"),
    ((2, "motorcycle", 0.84), "S2M08"),
    ((2, "car", 12.3), "S2C99"),
    ((1, "car", None), "S1C00"),
    ((0, "car", 2.0), "S0N00"),
]


def main():
    passed = total = 0
    for name, steps, expect in CASES:
        total += 1
        got = run_announcer(steps)
        ok = got == expect
        passed += ok
        print(f"{'OK ' if ok else 'NG '} 語音：{name}" + ("" if ok else f"  預期 {expect}，得到 {got}"))
    for args, expect in STATUS:
        total += 1
        got = status_line(*args)
        ok = got == expect and esp32_parse(got) is not None
        passed += ok
        print(f"{'OK ' if ok else 'NG '} 狀態：{args} → {got}" + ("" if ok else f"  預期 {expect}"))
    print(f"\n通過 {passed}/{total}")
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
