"""
成效評估：用偵測紀錄重播判斷規則，和人工標記的正確答案比對。

正確答案（影片名_truth.csv，由 label_events.py 產生）：
  kind   事件種類：持械、倒地、奔逃、聚集
  start  事件開始的秒數（例如剪刀舉起來的那一刻）
  end    事件結束的秒數
  note   備註

比對規則：
  同種類的警示，開始時間在 [start − 0.5 秒, end + 1 秒] 之內 → 偵測到，反應秒數 ＝ 警示開始 − start
  沒有對應到任何正確答案的警示 → 誤報
  同一件事被警示兩次以上 → 重複（不算誤報，但會讓保全一直被打擾，報告中要討論）

用法：
  python evaluate.py ../videos/demo_dets.csv
  python evaluate.py ../videos/我的影片.mp4                    影片要先用 analyze_video.py 分析過
  python evaluate.py ../videos/demo_dets.csv --set WEAPON_SUSTAIN_SEC=2
"""
import argparse
import csv
import sys
from pathlib import Path

import detlog
import threat_rules as tr

END_GAP_SEC = 1.0     # 同一種警示中斷超過這麼久，才算「結束」
EARLY_TOL = 0.5
LATE_TOL = 1.0
KIND_ORDER = ["持械", "奔逃", "倒地", "聚集"]


def fmt(v, digits=2):
    return "—" if v is None else f"{v:.{digits}f}"


def replay(frames):
    """把偵測紀錄逐格丟給規則，整理成「警示片段」：[{kind, level, start, end, detail}]"""
    analyzer = tr.ThreatAnalyzer()
    active, episodes = {}, []
    for t, h, _w, dets in frames:
        events, _ = analyzer.analyze(dets, t, h)
        now_kinds = {e.kind: e for e in events}
        for kind, ev in now_kinds.items():
            if kind in active:
                active[kind]["end"] = t
            else:
                active[kind] = {"kind": kind, "level": ev.level, "start": t, "end": t, "detail": ev.detail}
        for kind in list(active):
            if kind not in now_kinds and t - active[kind]["end"] > END_GAP_SEC:
                episodes.append(active.pop(kind))
    episodes.extend(active.values())
    return sorted(episodes, key=lambda e: (e["start"], e["kind"]))


def write_events(path, episodes):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["start", "end", "kind", "level", "detail"])
        for e in episodes:
            w.writerow([f"{e['start']:.2f}", f"{e['end']:.2f}", e["kind"], e["level"], e["detail"]])


def load_truth(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"找不到正確答案 {path.name}：請先用 label_events.py（8_label_video.bat）標記")
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            kind = (r.get("kind") or "").strip()
            if not kind:
                continue
            if kind not in tr.KINDS:
                raise SystemExit(f"{path.name} 有不認得的事件種類「{kind}」，只能是 {'、'.join(KIND_ORDER)}")
            rows.append({"kind": kind, "start": float(r["start"]), "end": float(r["end"]),
                         "note": r.get("note", "")})
    if not rows:
        raise SystemExit(f"{path.name} 是空的：請先標記")
    return sorted(rows, key=lambda r: r["start"])


def match(truths, episodes):
    """回傳 (每筆正確答案的結果, 誤報清單, 重複警示數)"""
    used = set()
    results = []
    for tr_row in truths:
        hit = None
        for i, ep in enumerate(episodes):
            if i in used or ep["kind"] != tr_row["kind"]:
                continue
            if tr_row["start"] - EARLY_TOL <= ep["start"] <= tr_row["end"] + LATE_TOL:
                hit = i
                break
        res = dict(tr_row, hit=hit is not None, latency=None, alarm=None)
        if hit is not None:
            used.add(hit)
            res["alarm"] = episodes[hit]["start"]
            res["latency"] = episodes[hit]["start"] - tr_row["start"]
        results.append(res)
    false_alarms, repeats = [], 0
    for i, ep in enumerate(episodes):
        if i in used:
            continue
        inside = any(t["kind"] == ep["kind"] and t["start"] - EARLY_TOL <= ep["start"] <= t["end"] + LATE_TOL
                     for t in truths)
        if inside:
            repeats += 1
        else:
            false_alarms.append(ep)
    return results, false_alarms, repeats


def score(results, false_alarms, minutes, kind=None):
    rs = [r for r in results if kind is None or r["kind"] == kind]
    fs = [f for f in false_alarms if kind is None or f["kind"] == kind]
    lat = [r["latency"] for r in rs if r["hit"]]
    hits = len(lat)
    return {
        "events": len(rs),
        "hits": hits,
        "missed": len(rs) - hits,
        "recall": hits / len(rs) if rs else None,
        "avg_latency": sum(lat) / hits if hits else None,
        "max_latency": max(lat) if lat else None,
        "false": len(fs),
        "false_per_10min": len(fs) / minutes * 10 if minutes else None,
    }


def duration_min(frames):
    if len(frames) < 2:
        return 0.0
    return (frames[-1][0] - frames[0][0]) / 60


def evaluate_file(dets_path, truth_path=None):
    frames = detlog.read_dets(dets_path)
    truth_path = truth_path or detlog.truth_path_for(dets_path)
    truths = load_truth(truth_path)
    episodes = replay(frames)
    results, false_alarms, repeats = match(truths, episodes)
    return {"frames": frames, "episodes": episodes, "results": results,
            "false_alarms": false_alarms, "repeats": repeats, "minutes": duration_min(frames)}


def print_report(name, ev):
    print(f"\n=== {name}（{ev['minutes']:.1f} 分鐘，{len(ev['episodes'])} 次警示）===")
    print("正確答案逐筆比對：")
    for r in ev["results"]:
        if r["hit"]:
            print(f"  ✔ {r['kind']} {r['start']:.1f}～{r['end']:.1f} 秒 → {r['alarm']:.1f} 秒警示（反應 {r['latency']:.1f} 秒）")
        else:
            print(f"  ✘ {r['kind']} {r['start']:.1f}～{r['end']:.1f} 秒 → 漏報")
    for f in ev["false_alarms"]:
        print(f"  ⚠ 誤報：{f['kind']} {f['start']:.1f}～{f['end']:.1f} 秒（{f['detail']}）")
    if ev["repeats"]:
        print(f"  ↻ 同一件事重複警示 {ev['repeats']} 次")
    print("\n種類  事件  偵測到  漏報  偵測率  平均反應秒數  最慢反應秒數  誤報")
    for kind in KIND_ORDER + [None]:
        s = score(ev["results"], ev["false_alarms"], ev["minutes"], kind)
        if kind and not s["events"] and not s["false"]:
            continue
        rate = "—" if s["recall"] is None else f"{s['recall']:.0%}"
        print(f"{kind or '合計'}  {s['events']:>4}  {s['hits']:>6}  {s['missed']:>4}  {rate:>6}  "
              f"{fmt(s['avg_latency']):>12}  {fmt(s['max_latency']):>12}  {s['false']:>4}")
    total = score(ev["results"], ev["false_alarms"], ev["minutes"])
    print(f"每 10 分鐘誤報：{fmt(total['false_per_10min'], 1)} 次")
    print("提醒：反應秒數是「警示成立」的時間；高風險事件還要再加上取消窗口 5 秒，LINE 才會發出。")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="比對偵測紀錄與正確答案")
    ap.add_argument("path", help="*_dets.csv，或已分析過的影片")
    ap.add_argument("--truth", help="正確答案檔（預設：同名的 _truth.csv）")
    ap.add_argument("--set", action="append", default=[], metavar="名稱=值")
    args = ap.parse_args()
    for item in args.set:
        name, value = tr.set_param(item)
        print(f"暫時設定 {name} = {value}")

    path = detlog.resolve(args.path)
    if path.suffix.lower() in detlog.VIDEO_EXT:
        dets = detlog.dets_path_for(path)
        if not dets.exists():
            raise SystemExit(f"還沒分析過這支影片：請先執行 analyze_video.py {path.name}")
        path = dets
    ev = evaluate_file(path, detlog.resolve(args.truth) if args.truth else None)
    print_report(path.name.replace("_dets.csv", ""), ev)


if __name__ == "__main__":
    main()
