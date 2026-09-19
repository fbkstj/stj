"""評估手勢辨識：用收集好的樣本，計算每個手勢的辨識率、混淆矩陣與誤觸率。

名詞：
  辨識率（召回率）：真的比這個手勢時，被認對的比例
  精確率：程式說是這個手勢時，真的是的比例
  誤觸率：「沒有指令」或「手太遠」的樣本，被當成指令手勢的比例（越低越好）

用法：
  python evaluate_gestures.py                                評估 data/ 裡所有 csv
  python evaluate_gestures.py data/samples_王小明.csv
  python evaluate_gestures.py --set straight_deg=30 --set thumb_out_ratio=0.6   暫時改門檻比較
結果另存到 output/gesture_eval_<時間>.csv（每一筆認錯的樣本）
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
from collections import Counter, defaultdict

import numpy as np

import gestures

HERE = os.path.dirname(os.path.abspath(__file__))
COMMANDS = ["open_palm", "point_right", "point_left", "thumb_up", "thumb_down", "v_sign", "fist"]
NON_COMMANDS = ["none", "too_far"]
LABELS = COMMANDS + NON_COMMANDS


def load_samples(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                w, h = float(r["width"]), float(r["height"])
                pts = np.array([[float(r[f"x{i}"]) * w, float(r[f"y{i}"]) * h] for i in range(21)])
                rows.append({"label": r["label"], "tag": r.get("tag", ""), "h": h, "pts": pts,
                             "file": os.path.basename(p)})
    return rows


def short(name):
    return gestures.GESTURE_NAMES.get(name, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--set", action="append", default=[], metavar="名稱=值")
    args = parser.parse_args()

    with open(os.path.join(HERE, args.config), encoding="utf-8") as f:
        cfg = json.load(f)
    for item in args.set:
        key, _, value = item.partition("=")
        if key not in cfg:
            raise SystemExit(f"config.json 沒有 {key} 這個設定")
        cfg[key] = json.loads(value)
        print(f"暫時設定 {key} = {cfg[key]}")

    paths = [p if os.path.isabs(p) else os.path.join(HERE, p) for p in args.files] or \
        sorted(glob.glob(os.path.join(HERE, "data", "*.csv")))
    if not paths:
        raise SystemExit("data/ 裡沒有樣本，請先執行 make_demo_samples.py 或 collect_samples.py")
    rows = load_samples(paths)
    for r in rows:
        r["pred"] = gestures.analyze(r["pts"], r["h"], cfg)[0]

    labels = [l for l in LABELS if any(r["label"] == l for r in rows)]
    cm = defaultdict(Counter)
    for r in rows:
        cm[r["label"]][r["pred"]] += 1
    preds = labels + sorted({r["pred"] for r in rows} - set(labels))

    print(f"樣本：{len(rows)} 筆（{', '.join(os.path.basename(p) for p in paths)}）\n")
    print(f"{'手勢':<10}{'筆數':>6}{'辨識率':>8}{'精確率':>8}")
    for l in labels:
        n = sum(cm[l].values())
        tp = cm[l][l]
        predicted = sum(cm[x][l] for x in cm)
        prec = tp / predicted if predicted else 0
        print(f"{short(l):<10}{n:>6}{tp / n:>8.1%}{prec:>8.1%}")
    acc = sum(cm[l][l] for l in labels) / len(rows)
    cmd_rows = [r for r in rows if r["label"] in COMMANDS]
    non_rows = [r for r in rows if r["label"] in NON_COMMANDS]
    print(f"\n整體準確率：{acc:.1%}")
    if cmd_rows:
        print(f"指令手勢辨識率：{sum(r['pred'] == r['label'] for r in cmd_rows) / len(cmd_rows):.1%}")
    if non_rows:
        false_cmd = sum(r["pred"] in COMMANDS for r in non_rows)
        print(f"誤觸率（非指令被當成指令）：{false_cmd / len(non_rows):.1%}（{false_cmd}/{len(non_rows)}）")
    wrong_cmd = sum(r["pred"] in COMMANDS and r["pred"] != r["label"] for r in cmd_rows)
    if cmd_rows:
        print(f"錯誤指令率（比 A 卻觸發 B）：{wrong_cmd / len(cmd_rows):.1%}（{wrong_cmd}/{len(cmd_rows)}）")

    print("\n=== 混淆矩陣（列＝真正的手勢，欄＝程式判斷）===")
    head = "".join(f"{gestures.SHORT_NAMES.get(p, p):>5}" for p in preds)
    print(f"{'':<10}{head}")
    for l in labels:
        print(f"{short(l):<10}" + "".join(f"{cm[l][p]:>6}" for p in preds))

    tags = sorted({r["tag"] for r in rows})
    if len(tags) > 1:
        print("\n=== 依標籤（距離、光線、人）===")
        for t in tags:
            sub = [r for r in rows if r["tag"] == t]
            print(f"{t:<20}{len(sub):>6} 筆  準確率 {sum(r['pred'] == r['label'] for r in sub) / len(sub):.1%}")

    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
    out = os.path.join(HERE, "output", f"gesture_eval_{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["檔案", "標籤", "真正的手勢", "程式判斷"])
        for r in rows:
            if r["pred"] != r["label"]:
                w.writerow([r["file"], r["tag"], short(r["label"]), short(r["pred"])])
    print("\n認錯的樣本清單：", out)


if __name__ == "__main__":
    main()
