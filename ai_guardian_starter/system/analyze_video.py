"""
分析一支錄好的演練影片：YOLO 找出人與危險物品 → 存成偵測紀錄 → 套用判斷規則 → 列出警示。

用法：
  python analyze_video.py ../videos/0917_穿堂演練1.mp4             分析並列出警示
  python analyze_video.py 影片.mp4 --show                          邊分析邊看畫面（q 停止）
  python analyze_video.py 影片.mp4 --save                          另存標註影片與警示截圖（人已打馬賽克）
  python analyze_video.py 影片.mp4 --redo                          偵測紀錄已存在也重新分析

產生：
  videos/影片名_dets.csv                 偵測紀錄（之後改門檻只要重播，不必重跑 YOLO）
  logs/影片名_events.csv                 這次的警示片段
  output/影片名_annotated.mp4            （--save）標註影片（人已打馬賽克）
  output/snapshots/影片名_秒數_事件.jpg  （--save）每次警示開始的截圖
有同名的 _truth.csv 時，會順便算成績。
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import detlog
import evaluate
import threat_rules as tr
from threat_rules import Detection, ThreatAnalyzer

DETECT_INTERVAL = 0.1        # 每 0.1 秒辨識一次（和即時監控差不多）
_FONTS = {}


def font(size):
    if size not in _FONTS:
        _FONTS[size] = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", size)
    return _FONTS[size]


def model_path():
    shared = detlog.ROOT / "yolov8n.pt"
    return str(shared) if shared.exists() else "yolov8n.pt"


def blur_people(frame, dets):
    """把每個人的框整個打馬賽克（還看得出姿勢，但認不出是誰）；危險物品的框保持清楚。
    沒被偵測到的人不會被遮住，對外使用前仍要逐張檢查。"""
    h, w = frame.shape[:2]
    keep = [(d.box, frame[max(0, int(d.box[1])):min(h, int(d.box[3])),
                          max(0, int(d.box[0])):min(w, int(d.box[2]))].copy())
            for d in dets if d.cls != tr.PERSON
            and (d.box[2] - d.box[0]) * (d.box[3] - d.box[1]) < 0.02 * w * h]   # 太大的框可能蓋到人臉，不保留
    for d in dets:
        if d.cls != tr.PERSON:
            continue
        x1, y1, x2, y2 = (int(v) for v in d.box)
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        if x2 - x1 < 4 or y2 - y1 < 4:
            continue
        block = max(8, (y2 - y1) // 16)
        roi = frame[y1:y2, x1:x2]
        small = cv2.resize(roi, (max(1, (x2 - x1) // block), max(1, (y2 - y1) // block)))
        frame[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    for box, patch in keep:
        if patch.size:
            frame[max(0, int(box[1])):max(0, int(box[1])) + patch.shape[0],
                  max(0, int(box[0])):max(0, int(box[0])) + patch.shape[1]] = patch


def draw(frame, dets, events, people, t):
    weapons = tr.weapon_classes()
    for d in dets:
        x1, y1, x2, y2 = (int(v) for v in d.box)
        if d.cls == tr.PERSON:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
        elif d.cls in weapons and d.conf >= tr.WEAPON_CONF:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 255), 1)
    kinds = "、".join(f"{e.kind}({e.level})" for e in events)
    text = f"{t:6.1f} 秒  人數 {people}  " + (f"【警示】{kinds}" if kinds else "監控中")
    color = (255, 60, 60) if events else (255, 255, 255)
    if events:
        cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 8)
    scale = max(1.0, frame.shape[1] / 1280)          # 高解析度影片的字也要看得清楚
    bar = int(46 * scale)
    frame[:bar] = (frame[:bar] * 0.25).astype(frame.dtype)   # 深色底，避免和攝影機原本的時間字疊在一起
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(img).text((int(12 * scale), int(8 * scale)), text, font=font(int(26 * scale)), fill=color,
                             stroke_width=max(2, int(2 * scale)), stroke_fill=(0, 0, 0))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def detect_video(video, dets_path, show=False, save=False):
    """用 YOLO 分析影片，寫出偵測紀錄。回傳偵測紀錄的路徑。"""
    from ultralytics import YOLO

    video = Path(video)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"無法開啟影片 {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    step = max(1, round(fps * DETECT_INTERVAL))
    model = YOLO(model_path())
    analyzer = ThreatAnalyzer()
    frames, writer = [], None
    snap_dir = detlog.OUTPUT / "snapshots"
    active = set()
    started = time.time()
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step:
            idx += 1
            continue
        t = idx / fps
        r = model.predict(frame, classes=tr.DETECT_CLASSES, conf=tr.DETECT_CONF,
                          imgsz=tr.IMG_SIZE, verbose=False)[0]
        dets = [Detection(int(b.cls[0]), float(b.conf[0]), tuple(b.xyxy[0].tolist())) for b in r.boxes]
        h, w = frame.shape[:2]
        frames.append((t, h, w, dets))
        events, people = analyzer.analyze(dets, t, h)
        if show or save:
            view = frame.copy()
            blur_people(view, dets)
            view = draw(view, dets, events, people, t)
            kinds = {e.kind for e in events}
            if save:
                if writer is None:
                    detlog.OUTPUT.mkdir(parents=True, exist_ok=True)
                    out = detlog.OUTPUT / f"{video.stem}_annotated.mp4"
                    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps / step, (w, h))
                writer.write(view)
                for k in kinds - active:
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    path = snap_dir / f"{video.stem}_{t:06.1f}_{k}.jpg"
                    cv2.imencode(".jpg", view)[1].tofile(str(path))   # 路徑有中文也能存
            active = kinds
            if show:
                cv2.imshow("analyze - q to stop", view)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("已停止，只保存到目前為止的結果")
                    break
        if total and len(frames) % 50 == 0:
            print(f"  {idx / total:.0%}", end="\r", flush=True)
        idx += 1
    cap.release()
    if writer:
        writer.release()
    if show:
        cv2.destroyAllWindows()
    if not frames:
        raise SystemExit("影片沒有任何畫面")
    spent = time.time() - started
    print(f"處理 {len(frames)} 個時間點，耗時 {spent:.0f} 秒（每秒 {len(frames) / max(spent, 1e-6):.1f} 張）")
    detlog.write_dets(dets_path, frames)
    return dets_path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="分析一支演練影片")
    ap.add_argument("video")
    ap.add_argument("--show", action="store_true", help="邊分析邊顯示畫面")
    ap.add_argument("--save", action="store_true", help="另存標註影片與警示截圖（人會打馬賽克）")
    ap.add_argument("--redo", action="store_true", help="偵測紀錄已存在也重新分析")
    ap.add_argument("--set", action="append", default=[], metavar="名稱=值")
    args = ap.parse_args()
    for item in args.set:
        name, value = tr.set_param(item)
        print(f"暫時設定 {name} = {value}")

    video = detlog.resolve(args.video)
    if not video.exists():
        raise SystemExit(f"找不到影片 {video}")
    dets_path = detlog.dets_path_for(video)
    if dets_path.exists() and not (args.redo or args.show or args.save):
        print(f"使用已存在的偵測紀錄 {dets_path.name}（要重新分析請加 --redo）")
    else:
        print(f"分析 {video.name} …")
        detect_video(video, dets_path, show=args.show, save=args.save)

    frames = detlog.read_dets(dets_path)
    episodes = evaluate.replay(frames)
    events_path = detlog.LOGS / f"{video.stem}_events.csv"
    evaluate.write_events(events_path, episodes)
    print(f"\n警示 {len(episodes)} 次（已存 {events_path}）：")
    for e in episodes:
        print(f"  {e['start']:7.1f}～{e['end']:7.1f} 秒  {e['kind']}（{e['level']}）  {e['detail']}")
    truth = detlog.truth_path_for(video)
    if truth.exists():
        evaluate.print_report(video.stem, evaluate.evaluate_file(dets_path, truth))
    else:
        print(f"\n還沒有正確答案 {truth.name}：用 8_label_video.bat 標記後就能算成績")


if __name__ == "__main__":
    main()
