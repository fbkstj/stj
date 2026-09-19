"""L13 作息異常偵測：用過去 N 天（預設 7）的紀錄學習平常作息，用簡單統計判斷，不需要 AI。

規則一「還沒起床」：平常第一次活動時間取平均，超過「平均＋容許分鐘」今天仍沒有任何活動 → 注意
規則二「活動量太少」：某時段（例如 12～17 點）結束後，今天的活動次數低於平常平均的 low_ratio 倍 → 注意
資料不足 N 天時不判斷，只記錄。同一種異常一天只通報一次。
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta

from modules.daily.summary import day_range


def minutes_of(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def fmt_min(m: float) -> str:
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def parse_block(block: str) -> tuple[int, int]:
    a, b = str(block).split("-")
    return int(a), int(b)


def activity_times(store, day, kinds, until=None) -> list[datetime]:
    from core.clock import parse_iso
    start, end = day_range(day)
    if until is not None and until < end:
        end = until
    return [parse_iso(e["time"]) for e in store.query(start, end, kind=kinds)]


def baseline(store, today, cfg) -> dict | None:
    """過去 N 天的作息。有任何一天完全沒有資料就回傳 None（資料不足）。"""
    kinds = cfg["activity_kinds"]
    days = [today - timedelta(days=i) for i in range(1, cfg["days"] + 1)]
    firsts, blocks = [], {b: [] for b in cfg["blocks"]}
    for d in days:
        times = activity_times(store, d, kinds)
        if not times:
            return None
        firsts.append(minutes_of(times[0]))
        for b in cfg["blocks"]:
            h1, h2 = parse_block(b)
            blocks[b].append(sum(1 for t in times if h1 <= t.hour < h2))
    return {"wake_mean": statistics.mean(firsts), "wake_sd": statistics.pstdev(firsts),
            "block_mean": {b: statistics.mean(v) for b, v in blocks.items()}, "days": len(days)}


def check(store, now: datetime, cfg: dict) -> tuple[list[tuple[str, str]], str]:
    """回傳 ([(異常代號, 訊息)], 說明)。"""
    today = now.date()
    base = baseline(store, today, cfg)
    if base is None:
        return [], f"資料不足 {cfg['days']} 天，先只記錄不判斷"
    alerts = []
    times = activity_times(store, today, cfg["activity_kinds"], until=now)
    limit = base["wake_mean"] + cfg["wake_tolerance_min"]
    if not times and minutes_of(now) >= limit:
        alerts.append(("wake", f"作息異常：平常約 {fmt_min(base['wake_mean'])} 開始活動，"
                               f"現在 {now:%H:%M} 還沒有偵測到任何活動"))
    for b in cfg["blocks"]:
        h1, h2 = parse_block(b)
        if now.hour < h2:
            continue
        usual = base["block_mean"][b]
        count = sum(1 for t in times if h1 <= t.hour < h2)
        if usual >= 3 and count < usual * cfg["low_ratio"]:
            alerts.append((f"low_{b}", f"作息異常：{h1}～{h2} 點活動 {count} 次，平常約 {usual:.0f} 次，明顯偏少"))
    note = (f"平常第一次活動約 {fmt_min(base['wake_mean'])}（±{base['wake_sd']:.0f} 分鐘），"
            f"超過 {fmt_min(limit)} 仍無活動就提醒")
    return alerts, note
