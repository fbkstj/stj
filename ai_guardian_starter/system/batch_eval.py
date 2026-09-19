"""
批次評估與參數實驗：資料夾裡每一份「有正確答案」的資料都評估一次，整理成一張成績表。

資料夾的放法：
  videos/0917_穿堂演練1.mp4            自己錄的影片
  videos/0917_穿堂演練1_truth.csv      label_events.py 標記的正確答案
  videos/0917_穿堂演練1_dets.csv       analyze_video.py 產生的偵測紀錄（沒有的話這裡會自動分析）
  videos/demo_dets.csv、demo_truth.csv 練習資料（make_demo_detections.py）

用法：
  python batch_eval.py                                         評估 videos 資料夾
  python batch_eval.py ../videos --set WEAPON_SUSTAIN_SEC=2 --tag sustain2
  python batch_eval.py --sweep WEAPON_CONF=0.25,0.35,0.5       同一個設定換幾個值，整理成比較表

結果（可用 Excel 開啟）：
  output/summary_<標籤>_<時間>.csv    每份資料一列，最後是合計與各事件種類
  output/sweep_<設定>_<時間>.csv      參數比較表
門檻不會被改到：--set 與 --sweep 只在這次執行有效。
"""
import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import detlog
import evaluate
import threat_rules as tr


def find_jobs(folder):
    """回傳 [(名稱, 偵測紀錄, 正確答案, 影片或 None)]，以及缺資料而跳過的名稱。"""
    jobs, skipped = [], []
    for truth in sorted(folder.glob("*_truth.csv")):
        name = truth.name[:-len("_truth.csv")]
        dets = folder / f"{name}_dets.csv"
        video = next((folder / f"{name}{ext}" for ext in detlog.VIDEO_EXT if (folder / f"{name}{ext}").exists()), None)
        if dets.exists() or video:
            jobs.append((name, dets, truth, video))
        else:
            skipped.append(name)
    return jobs, skipped


def ensure_dets(jobs):
    for name, dets, _truth, video in jobs:
        if not dets.exists():
            print(f"{name}：還沒有偵測紀錄，先用 YOLO 分析影片（需要幾分鐘）…")
            import analyze_video
            analyze_video.detect_video(video, dets)


def run_all(jobs):
    """用目前的門檻評估每份資料。"""
    rows, all_results, all_false, total_min = [], [], [], 0.0
    for name, dets, truth, _video in jobs:
        ev = evaluate.evaluate_file(dets, truth)
        s = evaluate.score(ev["results"], ev["false_alarms"], ev["minutes"])
        rows.append(row_of(name, s, ev["minutes"], ev["repeats"]))
        all_results += ev["results"]
        all_false += ev["false_alarms"]
        total_min += ev["minutes"]
    total = evaluate.score(all_results, all_false, total_min)
    repeats = sum(int(r["重複警示"]) for r in rows)
    rows.append(row_of("【合計】", total, total_min, repeats))
    for kind in evaluate.KIND_ORDER:
        s = evaluate.score(all_results, all_false, total_min, kind)
        if s["events"] or s["false"]:
            rows.append(row_of(f"【{kind}】", s, total_min, ""))
    return rows, total


def row_of(name, s, minutes, repeats):
    return {
        "資料": name,
        "事件數": s["events"],
        "偵測到": s["hits"],
        "漏報": s["missed"],
        "偵測率": "—" if s["recall"] is None else f"{s['recall']:.0%}",
        "平均反應秒數": evaluate.fmt(s["avg_latency"]),
        "最慢反應秒數": evaluate.fmt(s["max_latency"]),
        "誤報": s["false"],
        "重複警示": repeats,
        "分鐘數": evaluate.fmt(minutes, 1),
        "每10分鐘誤報": evaluate.fmt(s["false_per_10min"], 1),
    }


def print_table(rows):
    keys = list(rows[0])
    print("  ".join(keys))
    for r in rows:
        print("  ".join(str(r[k]) for k in keys))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="批次評估與參數實驗")
    ap.add_argument("folder", nargs="?", default="videos")
    ap.add_argument("--set", action="append", default=[], metavar="名稱=值", help="暫時修改門檻，可重複使用")
    ap.add_argument("--sweep", metavar="名稱=值1,值2,...", help="同一個門檻換幾個值比較")
    ap.add_argument("--tag", default="base", help="這次實驗的名稱，會放在檔名裡")
    args = ap.parse_args()

    for item in args.set:
        name, value = tr.set_param(item)
        print(f"暫時設定 {name} = {value}")
    folder = detlog.resolve(args.folder)
    if not folder.is_dir():
        raise SystemExit(f"找不到資料夾 {folder}")
    jobs, skipped = find_jobs(folder)
    if skipped:
        print("找不到影片或偵測紀錄，先跳過：", "、".join(skipped))
    if not jobs:
        raise SystemExit("沒有可以評估的資料：先執行 make_demo_detections.py，或標記自己的影片")
    ensure_dets(jobs)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.sweep:
        name, _, values = args.sweep.partition("=")
        sweep_rows = []
        for v in [x for x in values.split(",") if x.strip()]:
            key, val = tr.set_param(f"{name}={v}")
            _rows, total = run_all(jobs)
            sweep_rows.append({key: val, **{k: v2 for k, v2 in row_of("", total, 0, "").items()
                                             if k not in ("資料", "分鐘數", "重複警示")},
                               "每10分鐘誤報": evaluate.fmt(total["false_per_10min"], 1)})
        print(f"\n參數比較：{name.upper()}（其他門檻不變）")
        print_table(sweep_rows)
        out = detlog.OUTPUT / f"sweep_{name.upper()}_{stamp}.csv"
        write_csv(out, sweep_rows)
        print(f"\n已存：{out}")
        return

    rows, _total = run_all(jobs)
    print(f"\n成績表（{args.tag}）")
    print_table(rows)
    out = detlog.OUTPUT / f"summary_{args.tag}_{stamp}.csv"
    write_csv(out, rows)
    with open(out.with_suffix(".json"), "w", encoding="utf-8") as f:
        json.dump({"tag": args.tag, "folder": str(folder), "params": tr.current_params(),
                   "data": [j[0] for j in jobs]}, f, ensure_ascii=False, indent=2)
    print(f"\n已存：{out}（這次的門檻存在同名 .json）")


if __name__ == "__main__":
    main()
