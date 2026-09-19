"""比較「只用白手杖」與「白手杖＋警示帽」的障礙路線測試結果。

先把每一趟測試記在 trials.csv：
  tester  受測者代號（不要寫真實姓名）
  mode    cane（只用手杖）或 cane+hat（手杖加帽子）
  time_sec        走完路線的秒數
  head_hits       頭部或胸口碰到懸掛障礙物的次數
  ground_hits     腳或身體碰到地面障礙物的次數
  warnings        帽子發出警示的次數（只用手杖時填 0）
  false_alarms    沒有障礙卻警示的次數（只用手杖時填 0）

用法：python evaluate_trials.py            讀取 trials.csv
      python evaluate_trials.py my.csv
"""
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDS = ["time_sec", "head_hits", "ground_hits", "warnings", "false_alarms"]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "trials.csv")
    groups = defaultdict(list)
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            groups[row["mode"].strip()].append({k: float(row[k]) for k in FIELDS})
    if not groups:
        raise SystemExit("trials.csv 沒有資料")

    print(f"{'模式':<10}{'趟數':>6}{'平均秒數':>10}{'頭部碰撞/趟':>12}{'地面碰撞/趟':>12}{'誤報/趟':>9}")
    summary = {}
    for mode, rows in groups.items():
        n = len(rows)
        avg = {k: sum(r[k] for r in rows) / n for k in FIELDS}
        summary[mode] = avg
        print(f"{mode:<10}{n:>6}{avg['time_sec']:>10.1f}{avg['head_hits']:>12.2f}"
              f"{avg['ground_hits']:>12.2f}{avg['false_alarms']:>9.2f}")

    if "cane" in summary and "cane+hat" in summary:
        a, b = summary["cane"], summary["cane+hat"]
        print("\n=== 加上警示帽的變化 ===")
        if a["head_hits"] > 0:
            print(f"頭部碰撞減少 {(1 - b['head_hits'] / a['head_hits']):.0%}")
        else:
            print("只用手杖時沒有頭部碰撞，請檢查路線是否有懸掛障礙物")
        print(f"完成時間變化 {b['time_sec'] - a['time_sec']:+.1f} 秒")
        print(f"地面碰撞變化 {b['ground_hits'] - a['ground_hits']:+.2f} 次/趟")
        print(f"平均每趟誤報 {b['false_alarms']:.2f} 次")
    print("\n提醒：趟數太少時差異可能只是巧合，每種模式至少各測 10 趟，並輪流交換順序。")


if __name__ == "__main__":
    main()
