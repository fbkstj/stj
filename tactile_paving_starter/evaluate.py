"""步驟 4：計算偵測準確率。

先看一遍測試影片，把「導盲磚真的被占用」的時段記在 ground_truth.csv：
    start_sec,end_sec,note
    12,40,機車停放
    65,90,紙箱

再用同一支影片執行 paving_monitor.py，產生 output/state_log.csv，然後執行：
    python evaluate.py
    python evaluate.py --truth ground_truth.csv --state output/state_log.csv --min-event 30

輸出：
  - 逐秒比對：正確率、精確率、召回率、F1
  - 事件比對：真實事件中，有幾件被系統發出警示（持續時間不到 --min-event 秒的不列入）
"""
import argparse
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read_truth(path):
    spans = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            spans.append((float(row["start_sec"]), float(row["end_sec"]), row.get("note", "")))
    return spans


def read_state(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sec = int(float(row["time"]))
            except ValueError:
                raise SystemExit("state_log.csv 的時間不是秒數：評估請用「影片檔」當來源執行 paving_monitor.py")
            rows.append((sec, int(row["occupied"]), int(row["alert"])))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", default=os.path.join(HERE, "ground_truth.csv"))
    parser.add_argument("--state", default=os.path.join(HERE, "output", "state_log.csv"))
    parser.add_argument("--min-event", type=float, default=30, help="與 config.json 的 occupy_seconds 相同")
    args = parser.parse_args()

    truth = read_truth(args.truth)
    state = read_state(args.state)
    in_truth = lambda s: any(a <= s < b for a, b, _ in truth)

    tp = fp = fn = tn = 0
    for sec, occ, _alert in state:
        gt = in_truth(sec)
        if occ and gt:
            tp += 1
        elif occ and not gt:
            fp += 1
        elif not occ and gt:
            fn += 1
        else:
            tn += 1
    total = tp + fp + fn + tn
    acc = (tp + tn) / total if total else 0
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0

    print("=== 逐秒比對 ===")
    print(f"總秒數 {total}｜TP {tp}  FP {fp}  FN {fn}  TN {tn}")
    print(f"正確率 Accuracy  = {acc:.1%}  （判斷對的秒數比例）")
    print(f"精確率 Precision = {prec:.1%}  （系統說被占用時，真的被占用的比例；越低代表誤報越多）")
    print(f"召回率 Recall    = {rec:.1%}  （真的被占用時，系統有抓到的比例；越低代表漏報越多）")
    print(f"F1               = {f1:.1%}")

    alerts = [sec for sec, _o, a in state if a]
    print("\n=== 事件比對 ===")
    counted = hit = 0
    for a, b, note in truth:
        if b - a < args.min_event:
            print(f"  {a:>6.0f}~{b:<6.0f} {note}：持續不到 {args.min_event:.0f} 秒，不列入")
            continue
        counted += 1
        ok = any(a <= s <= b + 5 for s in alerts)
        hit += ok
        print(f"  {a:>6.0f}~{b:<6.0f} {note}：{'有發出警示' if ok else '漏報'}")
    if counted:
        print(f"事件偵測率 {hit}/{counted} = {hit / counted:.1%}")

    # 警示發生在任何真實占用時段以外 → 誤報事件
    false_alarm_secs = [s for s in alerts if not any(a <= s <= b + 5 for a, b, _ in truth)]
    print(f"誤報的警示秒數：{len(false_alarm_secs)}")


if __name__ == "__main__":
    main()
