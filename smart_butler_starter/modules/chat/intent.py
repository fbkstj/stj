"""L6 意圖辨識：把「幫我開一下客廳的燈」轉成 {裝置: 客廳燈, 動作: on}。

做法（規則式，不需要 AI，結果可以預測、可以測試）：
1. 去掉「幫我、請、一下、的」等不影響意思的字
2. 找動作詞（關掉、打開、暗一點…）
3. 找裝置：比對名稱與別名（取最長的那個）；找不到時，用「房間＋燈」推測
"""
from __future__ import annotations

import re
from dataclasses import dataclass

FILLERS = ["麻煩你", "麻煩", "可以", "幫我", "幫忙", "請你", "請", "一下", "給我", "我要", "我想", "的", "把",
           "啦", "喔", "哦", "吧", "呢", "嗎", "耶", "好不好", "謝謝", "管家", "阿娜", "Aina", "aina"]

# (動作, 關鍵詞)。順序很重要：先比對較長、較特別的詞
ACTION_WORDS = [
    ("status", ["有沒有開", "有沒有關", "開著嗎", "關了沒", "開了沒", "開著沒", "現在狀態", "是開著", "是關著"]),
    ("dim", ["暗一點", "調暗", "太亮", "暗一些", "小聲", "調小", "弱一點"]),
    ("bright", ["亮一點", "調亮", "太暗", "亮一些", "大聲", "調大", "強一點"]),
    ("off", ["關掉", "關起來", "關閉", "關上", "熄掉", "熄燈", "停掉", "不要開", "關"]),
    ("on", ["打開", "開啟", "啟動", "開起來", "點亮", "開"]),
]
ACTION_NAMES = {"on": "打開", "off": "關掉", "dim": "調暗", "bright": "調亮", "status": "查詢"}
TYPE_WORDS = {"light": ["燈"], "fan": ["風扇", "電扇"], "aircon": ["冷氣", "空調"], "tv": ["電視"]}


@dataclass
class Intent:
    device: str | None       # 裝置名稱；None 代表不是家電指令
    action: str | None       # on／off／dim／bright／status
    dangerous: bool = False
    reason: str = ""         # 看不懂時的說明


def normalize(text: str) -> str:
    t = re.sub(r"[\s，。！？、,.!?~～]", "", text)
    for f in FILLERS:
        t = t.replace(f, "")
    return t


def find_action(t: str) -> str | None:
    for action, words in ACTION_WORDS:
        if any(w in t for w in words):
            return action
    return None


def find_device(t: str, devices: list[dict]) -> dict | None:
    best, best_len = None, 0
    for d in devices:
        for name in [d["name"], *d.get("aliases", [])]:
            n = normalize(name)
            if n and n in t and len(n) > best_len:
                best, best_len = d, len(n)
    if best:
        return best
    # 沒有直接說裝置名稱：用「房間」＋「類型」推測，例如「客廳暗一點」「臥室的燈」
    rooms = [d for d in devices if d.get("room") and d["room"] in t]
    for type_, words in TYPE_WORDS.items():
        if any(w in t for w in words):
            same = [d for d in (rooms or devices) if d.get("type") == type_]
            if len(same) == 1 or (rooms and same):
                return same[0]
    lights = [d for d in rooms if d.get("type") == "light"]
    if lights and find_action(t) in ("dim", "bright"):
        return lights[0]
    return None


def parse(text: str, devices: list[dict]) -> Intent:
    t = normalize(text)
    action = find_action(t)
    device = find_device(t, devices)
    if device is None:
        if action and any(w in t for words in TYPE_WORDS.values() for w in words):
            return Intent(None, action, reason="不確定是哪一個房間的設備，請說清楚，例如「客廳燈」")
        return Intent(None, None, reason="不是家電指令")
    if action is None:
        return Intent(device["name"], None, bool(device.get("dangerous")), reason="要打開還是關掉呢？")
    return Intent(device["name"], action, bool(device.get("dangerous")))
