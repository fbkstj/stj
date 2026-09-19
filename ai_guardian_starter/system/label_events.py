"""
標記正確答案：播放演練影片，事件開始時按一次、結束時再按一次同一個鍵。

按鍵：
  1  持械（剪刀舉起來 → 放下）      2  倒地（倒下 → 站起來）
  3  奔逃（開始跑 → 跑出畫面）      4  聚集（人數到 15 人 → 散開）
  u      取消上一個動作
  p      暫停／繼續
  a／d   倒退／快轉 3 秒
  ,／.   暫停時往前／往後一格
  q      存檔並離開（還沒結束的事件，以目前時間當作結束）

用法：python label_events.py ../videos/0917_穿堂演練1.mp4     存成 videos/0917_穿堂演練1_truth.csv
      python label_events.py 影片.mp4 --out 答案_B.csv           兩人各自標記再比對時使用

標記時只看影片，不要先看程式的警示結果，避免影響判斷。
"""
import argparse
import csv
import sys

import cv2

import detlog

KEYS = {ord("1"): "持械", ord("2"): "倒地", ord("3"): "奔逃", ord("4"): "聚集"}
SHORT = {"持械": "WEAPON", "倒地": "FALL", "奔逃": "RUN", "聚集": "CROWD"}


def load_existing(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [[r["kind"], float(r["start"]), float(r["end"]), r.get("note", "")]
                for r in csv.DictReader(f) if (r.get("kind") or "").strip()]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", help="答案檔；預設存在影片旁邊，檔名加上 _truth")
    args = ap.parse_args()

    video = detlog.resolve(args.video)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit("無法開啟影片")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_path = detlog.resolve(args.out) if args.out else detlog.truth_path_for(video)

    marks = load_existing(out_path)          # [種類, 開始, 結束, 備註]
    opened = {}                              # 種類 -> 開始秒數
    history = []                             # 用來取消：("open", 種類) 或 ("close", 標記)
    if marks:
        print(f"讀到之前的 {len(marks)} 筆標記，會接著標記")
    paused = False
    idx = 0
    ok, frame = cap.read()
    while ok:
        t = idx / fps
        view = frame.copy()
        if view.shape[1] > 1280:
            view = cv2.resize(view, None, fx=1280 / view.shape[1], fy=1280 / view.shape[1])
        cv2.rectangle(view, (0, 0), (view.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(view, f"t={t:6.2f}s  done={len(marks)}  1weapon 2fall 3run 4crowd (press at start AND end)  "
                          "u=undo p=pause a/d q=save", (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        for i, (kind, t0) in enumerate(opened.items()):
            cv2.putText(view, f"{SHORT[kind]} since {t0:.1f}s", (8, 60 + i * 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 220, 255), 2)
        cv2.imshow("Label Events", view)
        key = cv2.waitKey(0 if paused else max(1, int(1000 / fps))) & 0xFF

        seek = None
        if key in (ord("q"), 27):
            break
        if key in KEYS:
            kind = KEYS[key]
            if kind in opened:
                mark = [kind, round(opened.pop(kind), 2), round(t, 2), ""]
                marks.append(mark)
                history.append(("close", mark))
                print(f"{kind}：{mark[1]:.2f}～{mark[2]:.2f} 秒")
            else:
                opened[kind] = t
                history.append(("open", kind))
                print(f"{kind} 開始：{t:.2f} 秒（結束時再按一次）")
        elif key == ord("u") and history:
            action, item = history.pop()
            if action == "open":
                opened.pop(item, None)
                print(f"取消：{item} 的開始")
            else:
                marks.remove(item)
                opened[item[0]] = item[1]
                print(f"取消：{item[0]} 的結束（回到進行中）")
        elif key == ord("p"):
            paused = not paused
        elif key == ord("a"):
            seek = idx - int(3 * fps)
        elif key == ord("d"):
            seek = idx + int(3 * fps)
        elif key == ord(",") and paused:
            seek = idx - 1
        elif key == ord(".") and paused:
            seek = idx + 1

        if seek is not None:
            idx = max(0, min(total - 1, seek))
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
        elif not paused:
            ok, frame = cap.read()
            idx += 1
    cap.release()
    cv2.destroyAllWindows()

    end_t = idx / fps
    for kind, t0 in opened.items():
        marks.append([kind, round(t0, 2), round(end_t, 2), "結束時間為存檔時的時間"])
    if not marks:
        print("沒有標記，不存檔")
        return
    if out_path.exists():
        out_path.replace(out_path.with_name(out_path.name + ".bak"))
        print("舊檔已改名為", out_path.name + ".bak")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["kind", "start", "end", "note"])
        for m in sorted(marks, key=lambda m: m[1]):
            w.writerow(m)
    print(f"已存 {len(marks)} 筆標記到 {out_path}")


if __name__ == "__main__":
    main()
