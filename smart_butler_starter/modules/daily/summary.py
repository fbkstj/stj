"""L11 每日平安回報：只從事件資料庫統計，不需要新的感測器。

統計內容：活動時段、服藥（準時／延遲／漏服）、訪客次數、注意與緊急事件數。
漏服的定義：發過「逾時未確認」（meds_overdue），之後當天都沒有「已服藥」（meds_taken）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.clock import TAIPEI, parse_iso

WEEKDAYS = "一二三四五六日"
ACTIVITY_KINDS = ["activity", "device", "chat", "meds_taken", "board"]


def day_range(day) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=TAIPEI)
    return start, start + timedelta(days=1)


def collect(store, day, until=None, activity_kinds=None) -> dict:
    start, end = day_range(day)
    if until is not None and until < end:
        end = until
    kinds = activity_kinds or ACTIVITY_KINDS
    acts = store.query(start, end, kind=kinds)
    taken = store.query(start, end, kind="meds_taken")
    overdue = store.query(start, end, kind="meds_overdue")
    taken_keys = {(e["data"].get("dose"), e["data"].get("due")) for e in taken}
    missed = [e for e in overdue if (e["data"].get("dose"), e["data"].get("due")) not in taken_keys]
    others = [e for e in store.query(start, end) if e["kind"] not in ("daily_summary",)]
    return {
        "date": day,
        "first_activity": parse_iso(acts[0]["time"]) if acts else None,
        "last_activity": parse_iso(acts[-1]["time"]) if acts else None,
        "activity_count": len(acts),
        "meds_ontime": sum(1 for e in taken if e["data"].get("status") == "準時"),
        "meds_late": sum(1 for e in taken if e["data"].get("status") == "延遲"),
        "meds_missed": len(missed),
        "missed_names": [f"{e['data'].get('dose')} {parse_iso(e['data']['due']):%H:%M}" for e in missed if e["data"].get("due")],
        "visits": sum(1 for e in others if e["kind"] == "visit"),
        "warn": sum(1 for e in others if e["level"] == "warn"),
        "urgent": sum(1 for e in others if e["level"] == "urgent"),
    }


def format_summary(s: dict, name: str = "智慧管家") -> str:
    d = s["date"]
    lines = []
    if s["meds_missed"] or s["urgent"]:
        flags = []
        if s["urgent"]:
            flags.append(f"緊急事件 {s['urgent']} 件")
        if s["meds_missed"]:
            flags.append(f"漏服藥 {s['meds_missed']} 次")
        lines.append("⚠️ 今天有" + "、".join(flags) + "，請特別留意")
    lines.append(f"【每日平安回報】{d.month}/{d.day}（{WEEKDAYS[d.weekday()]}）")
    if s["first_activity"]:
        lines.append(f"・活動：{s['first_activity']:%H:%M}～{s['last_activity']:%H:%M}，共 {s['activity_count']} 筆")
    else:
        lines.append("・活動：今天沒有偵測到活動")
    meds = f"・服藥：準時 {s['meds_ontime']}、延遲 {s['meds_late']}、漏服 {s['meds_missed']}"
    if s["missed_names"]:
        meds += "（" + "、".join(s["missed_names"]) + "）"
    lines.append(meds)
    lines.append(f"・訪客：{s['visits']} 次")
    lines.append(f"・注意 {s['warn']} 件、緊急 {s['urgent']} 件")
    return "\n".join(lines)
