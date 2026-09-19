"""比對程式的警示紀錄與人工標記的正確答案，計算「提早幾秒警示」、漏報與誤報。

正確答案 CSV（用 label_events.py 標記，或自己用 Excel 填）：
  pass_time  車輛從騎士旁邊經過的秒數
  vehicle    車種（car、motorcycle、bus、truck，可以空白）
  note       備註

判斷方式：
  - 經過前 max_lead 秒內有開始警示 → 成功，提早秒數＝經過時間－警示開始時間
  - 經過前沒有警示 → 漏報
  - 警示開始後，沒有任何車在 max_lead 秒內經過 → 誤報

用法：
  python evaluate.py --truth videos/demo_truth.csv              比對 logs/ 裡最新的紀錄
  python evaluate.py --truth videos/A_truth.csv --log logs/A_20260917_130000.csv
"""
import argparse
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def load_truth(path):
    """回傳 [(經過秒數, 車種), ...]，依時間排序。"""
    with open(path, encoding="utf-8-sig") as f:
        rows = [(float(r["pass_time"]), (r.get("vehicle") or "").strip() or "未分類")
                for r in csv.DictReader(f) if (r.get("pass_time") or "").strip()]
    return sorted(rows)


def load_alerts(path):
    """回傳 (警示開始時間, 紅燈開始時間)。"""
    alerts, danger = [], []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["event"] == "alert_on":
                alerts.append(float(r["time"]))
            if r["event"] in ("alert_on", "escalate") and r["level"] == "2":
                danger.append(float(r["time"]))
    return alerts, danger


def load_alert_vehicles(path):
    """回傳 {警示開始時間: 觸發的車種}，用來檢查語音說的車種對不對。"""
    with open(path, encoding="utf-8-sig") as f:
        return {float(r["time"]): r["vehicle"] for r in csv.DictReader(f) if r["event"] == "alert_on"}


def same_group(a, b, big=("bus", "truck")):
    """車種是否屬於同一個語音分類（公車、貨車都算大型車）。"""
    return (a in big and b in big) or a == b


def match(truth, alerts, danger, max_lead=8.0, late=0.3, vehicles=None):
    """逐一比對每次經過，回傳每一列的結果與誤報時間。
    vehicles：load_alert_vehicles 的結果，有給就會比對車種。"""
    rows, used = [], set()
    for p, vehicle in truth:
        cands = [a for a in alerts if p - max_lead <= a <= p + late]
        dcands = [a for a in danger if p - max_lead <= a <= p + late]
        used.update(cands)
        first = min(cands) if cands else None
        said = (vehicles or {}).get(first) if first is not None else None
        rows.append({
            "pass_time": p,
            "vehicle": vehicle,
            "alert_time": first,
            "lead": p - first if cands else None,
            "danger_lead": p - min(dcands) if dcands else None,
            "alert_vehicle": said,
            "type_ok": (same_group(said, vehicle) if said and vehicle != "未分類" else None),
        })
    false_alarms = [a for a in alerts if a not in used]
    return rows, false_alarms


def score(rows):
    """把比對結果整理成成績：次數、成功率、平均與最短提早秒數。"""
    leads = [r["lead"] for r in rows if r["lead"] is not None]
    dleads = [r["danger_lead"] for r in rows if r["danger_lead"] is not None]
    n = len(rows)
    typed = [r["type_ok"] for r in rows if r.get("type_ok") is not None]
    return {
        "type_checked": len(typed),
        "type_correct": sum(typed),
        "passes": n,
        "hits": len(leads),
        "missed": n - len(leads),
        "recall": len(leads) / n if n else 0.0,
        "avg_lead": sum(leads) / len(leads) if leads else None,
        "min_lead": min(leads) if leads else None,
        "avg_danger_lead": sum(dleads) / len(dleads) if dleads else None,
    }


def by_vehicle(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["vehicle"], []).append(r)
    return {k: score(v) for k, v in sorted(groups.items())}


def fmt(v, digits=2):
    return "—" if v is None else f"{v:.{digits}f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", default="videos/demo_truth.csv")
    parser.add_argument("--log", help="警示紀錄；不填就用 logs/ 裡最新的檔案")
    parser.add_argument("--max-lead", type=float, default=8.0, help="警示最多可以提早幾秒（預設 8）")
    parser.add_argument("--late", type=float, default=0.3, help="經過後幾秒內的警示仍算數（預設 0.3）")
    args = parser.parse_args()

    if args.log:
        log_path = resolve(args.log)
    else:
        logs = sorted(glob.glob(os.path.join(HERE, "logs", "*.csv")), key=os.path.getmtime)
        if not logs:
            raise SystemExit("logs/ 裡沒有紀錄，請先執行 rear_alert.py")
        log_path = logs[-1]

    truth = load_truth(resolve(args.truth))
    if not truth:
        raise SystemExit("正確答案檔沒有資料，請先用 label_events.py 標記")
    alerts, danger = load_alerts(log_path)
    rows, false_alarms = match(truth, alerts, danger, args.max_lead, args.late, load_alert_vehicles(log_path))
    s = score(rows)

    print("警示紀錄：", os.path.relpath(log_path, HERE))
    print(f"{'經過時間':>8}  {'車種':<10}{'警示開始':>8}  {'提早秒數':>8}  {'紅燈提早':>8}  {'程式判斷車種'}")
    for r in rows:
        alert = fmt(r["alert_time"]) if r["alert_time"] is not None else "漏報"
        said = r["alert_vehicle"] or ""
        mark = "" if r["type_ok"] is None else ("（對）" if r["type_ok"] else "（錯）")
        print(f"{r['pass_time']:>8.2f}  {r['vehicle']:<10}{alert:>8}  {fmt(r['lead']):>8}  {fmt(r['danger_lead']):>8}"
              f"  {said}{mark}")

    print("\n=== 結果 ===")
    print(f"真的逼近：{s['passes']} 次，成功警示 {s['hits']} 次（{s['recall']:.0%}），漏報 {s['missed']} 次")
    if s["avg_lead"] is not None:
        print(f"平均提早 {s['avg_lead']:.2f} 秒（最短 {s['min_lead']:.2f} 秒）")
    if s["avg_danger_lead"] is not None:
        print(f"紅燈平均提早 {s['avg_danger_lead']:.2f} 秒")
    if s["type_checked"]:
        print(f"車種判斷（語音說的車種，公車與貨車都算大型車）：{s['type_correct']}/{s['type_checked']} 正確"
              f"（{s['type_correct'] / s['type_checked']:.0%}）")
    minutes = None
    summary_path = os.path.splitext(log_path)[0] + ".json"
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            minutes = json.load(f)["duration_sec"] / 60
    rate = f"，約每 10 分鐘 {len(false_alarms) / minutes * 10:.1f} 次" if minutes else ""
    print(f"誤報：{len(false_alarms)} 次{rate}" +
          (f"（時間：{', '.join(f'{a:.1f}' for a in false_alarms)}）" if false_alarms else ""))

    groups = by_vehicle(rows)
    if len(groups) > 1:
        print("\n=== 依車種 ===")
        for k, g in groups.items():
            print(f"{k:<12}經過 {g['passes']} 次、成功 {g['hits']} 次、平均提早 {fmt(g['avg_lead'])} 秒")
    print("\n提醒：只有一兩段影片時結果不穩定，請用不同路段、天氣、時段的影片，至少標記 30 次經過。")


if __name__ == "__main__":
    main()
