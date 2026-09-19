"""批次分析：把資料夾裡每支「有正確答案」的影片都分析一次，整理成一張成績表。

資料夾的放法（label_events.py 會自動用這個檔名存答案）：
  videos/0917_早上_中正路.mp4
  videos/0917_早上_中正路_truth.csv

用法：
  python batch_run.py videos                                   用 config.json 的設定
  python batch_run.py videos --set ttc_warn=3 --tag warn3      暫時改參數（不會改到 config.json）
  python batch_run.py videos --set imgsz=960 --set confirm_count=1 --tag test2

結果：
  output/summary_<標籤>_<時間>.csv    每支影片一列、最後是合計與各車種（可用 Excel 開啟）
  output/summary_<標籤>_<時間>.json   這次用的完整設定
"""
import argparse
import csv
import datetime as dt
import json
import os
import subprocess
import sys

import evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv")


def parse_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def row_of(name, s, false_alarms, minutes, fps):
    return {
        "影片": name,
        "經過次數": s["passes"],
        "成功警示": s["hits"],
        "漏報": s["missed"],
        "成功率": f"{s['recall']:.0%}",
        "平均提早秒數": evaluate.fmt(s["avg_lead"]),
        "最短提早秒數": evaluate.fmt(s["min_lead"]),
        "紅燈平均提早": evaluate.fmt(s["avg_danger_lead"]),
        "車種正確": f"{s['type_correct']}/{s['type_checked']}" if s["type_checked"] else "—",
        "誤報": false_alarms,
        "影片分鐘數": evaluate.fmt(minutes, 1),
        "每10分鐘誤報": evaluate.fmt(false_alarms / minutes * 10 if minutes else None, 1),
        "處理速度(張/秒)": fps,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="videos")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--set", action="append", default=[], metavar="名稱=值", help="暫時修改設定，可重複使用")
    parser.add_argument("--tag", default="base", help="這次實驗的名稱，會放在檔名裡")
    args = parser.parse_args()

    folder = evaluate.resolve(args.folder)
    with open(evaluate.resolve(args.config), encoding="utf-8") as f:
        cfg = json.load(f)
    for item in args.set:
        key, _, value = item.partition("=")
        if key not in cfg:
            raise SystemExit(f"config.json 沒有 {key} 這個設定")
        cfg[key] = parse_value(value)
        print(f"暫時設定 {key} = {cfg[key]}")

    videos = sorted(f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXT))
    jobs, skipped = [], []
    for v in videos:
        truth = os.path.join(folder, os.path.splitext(v)[0] + "_truth.csv")
        (jobs if os.path.exists(truth) else skipped).append((v, truth))
    if skipped:
        print("沒有正確答案、先跳過：", "、".join(v for v, _ in skipped))
    if not jobs:
        raise SystemExit(f"{args.folder} 裡沒有「影片＋_truth.csv」的組合，請先用 2_label_video.bat 標記")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(HERE, "logs", f"batch_{args.tag}_{stamp}")
    os.makedirs(run_dir, exist_ok=True)
    cfg_path = os.path.join(run_dir, "config_used.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    table, all_rows, total_fa, total_min = [], [], 0, 0.0
    for i, (v, truth_path) in enumerate(jobs, 1):
        print(f"\n[{i}/{len(jobs)}] 分析 {v} …")
        log_path = os.path.join(run_dir, os.path.splitext(v)[0] + ".csv")
        r = subprocess.run([sys.executable, os.path.join(HERE, "rear_alert.py"), "--video", os.path.join(folder, v),
                            "--config", cfg_path, "--no-serial", "--no-sound", "--log", log_path], cwd=HERE)
        if r.returncode != 0:
            print("  分析失敗，跳過")
            continue
        with open(os.path.splitext(log_path)[0] + ".json", encoding="utf-8") as f:
            info = json.load(f)
        truth = evaluate.load_truth(truth_path)
        alerts, danger = evaluate.load_alerts(log_path)
        rows, fa = evaluate.match(truth, alerts, danger, vehicles=evaluate.load_alert_vehicles(log_path))
        minutes = info["duration_sec"] / 60
        table.append(row_of(v, evaluate.score(rows), len(fa), minutes, info["processing_fps"]))
        all_rows += rows
        total_fa += len(fa)
        total_min += minutes

    if not table:
        raise SystemExit("沒有任何影片分析成功")
    table.append(row_of("【合計】", evaluate.score(all_rows), total_fa, total_min, ""))
    for k, g in evaluate.by_vehicle(all_rows).items():
        row = row_of(f"【車種】{k}", g, 0, None, "")
        row["誤報"] = row["每10分鐘誤報"] = row["影片分鐘數"] = ""
        table.append(row)

    out_dir = os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"summary_{args.tag}_{stamp}.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    with open(os.path.splitext(out_path)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print("\n=== 成績表 ===")
    for row in table:
        print(f"{row['影片']:<24} 經過 {row['經過次數']:>3}  成功率 {row['成功率']:>5}  "
              f"平均提早 {row['平均提早秒數']:>5} 秒  誤報 {row['誤報']!s:>3}")
    print("\n成績表已存到：", out_path)


if __name__ == "__main__":
    main()
