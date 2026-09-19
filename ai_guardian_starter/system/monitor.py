"""
公共場所 AI 監控通報系統(原型)

多台攝影機 → YOLO 偵測(人/刀/棍棒) → 威脅規則判斷 → 分級通報(現場警報 / LINE)

用法:
  python monitor.py                 依 sources_config.py 開啟監控牆
  python monitor.py --no-line       不發 LINE(只在終端機顯示通報內容)
  python monitor.py --serial COM3   指定警示盒(ESP32)的序列埠;預設 auto 自動尋找,none 不使用
  python monitor.py --set WEAPON_SUSTAIN_SEC=1   暫時修改 threat_rules.py 的門檻
  python monitor.py --headless --seconds 30   無視窗測試

監控牆按鍵:C 取消誤報(高風險事件 5 秒取消窗口內)  Q 離開
警示盒:按下取消鈕等於按 C
"""
import argparse
import math
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

import alerter as alerter_mod
import threat_rules as tr
from alarm_link import AlarmLink
from alerter import Alerter
from sources import FrameSource
from sources_config import SOURCES
from threat_rules import Detection, ThreatAnalyzer, LEVEL_HIGH

# 優先用上一層（學生實作資料夾）的模型檔；沒有的話 ultralytics 會自動下載
_SHARED_MODEL = Path(__file__).resolve().parent.parent / "yolov8n.pt"
MODEL_PATH = str(_SHARED_MODEL) if _SHARED_MODEL.exists() else "yolov8n.pt"
TILE_W, TILE_H = 640, 360
FONT = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 20)
FONT_BIG = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 26)

COLOR_PERSON = (0, 200, 0)
COLOR_WEAPON = (0, 0, 255)


def put_text(img, items):
    """items: [(文字, (x, y), (B, G, R), font)] 一次轉 PIL 畫完,cv2.putText 不支援中文。"""
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    for text, xy, bgr, font in items:
        draw.text(xy, text, font=font, fill=bgr[::-1], stroke_width=2, stroke_fill=(0, 0, 0))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


class CameraState:
    def __init__(self, source):
        self.source = source
        self.analyzer = ThreatAnalyzer()
        self.last_frame_id = -1
        self.dets = []
        self.people = 0
        self.active = {}  # 事件種類 -> 最後成立時間(用來在畫面上顯示)


def detect(model, frame):
    r = model.predict(frame, classes=tr.DETECT_CLASSES, conf=tr.DETECT_CONF, imgsz=tr.IMG_SIZE, verbose=False)[0]
    return [Detection(int(b.cls[0]), float(b.conf[0]), tuple(b.xyxy[0].tolist())) for b in r.boxes]


def render_tile(cam, frame, now):
    h, w = frame.shape[:2]
    weapons = tr.weapon_classes()
    shown = [d for d in cam.dets
             if (d.cls == tr.PERSON and d.conf >= tr.PERSON_CONF)
             or (d.cls in weapons and d.conf >= tr.WEAPON_CONF)]
    for d in shown:
        x1, y1, x2, y2 = map(int, d.box)
        color = COLOR_WEAPON if d.cls in weapons else COLOR_PERSON
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, max(2, w // 400))
    tile = cv2.resize(frame, (TILE_W, TILE_H))
    s = TILE_W / w
    labels = [(f"{cam.source.name}  人數 {cam.people}", (10, 6), (255, 255, 255), FONT)]
    for d in shown:
        if d.cls in weapons:
            labels.append((f"{weapons[d.cls]} {d.conf:.2f}",
                           (int(d.box[0] * s), max(int(d.box[1] * s) - 26, 0)), COLOR_WEAPON, FONT))
    active = [(k, lv) for k, (t, lv) in cam.active.items() if now - t < 3]
    if active:
        high = any(lv == LEVEL_HIGH for _, lv in active)
        border = (0, 0, 255) if high else (0, 165, 255)
        if high and int(now * 4) % 2:  # 高風險紅框閃爍
            border = (0, 0, 120)
        cv2.rectangle(tile, (0, 0), (TILE_W - 1, TILE_H - 1), border, 8)
        text = "【警示】" + "、".join(f"{k}({lv})" for k, lv in active)
        labels.append((text, (10, TILE_H - 40), border, FONT_BIG))
    if not cam.source.online:
        labels.append(("訊號中斷", (TILE_W // 2 - 50, TILE_H // 2 - 15), (0, 0, 255), FONT_BIG))
    return put_text(tile, labels)


def compose_wall(tiles, alerter, now):
    cols = 1 if len(tiles) == 1 else 2
    rows = math.ceil(len(tiles) / cols)
    wall = np.zeros((rows * TILE_H + 50, cols * TILE_W, 3), np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        wall[r * TILE_H:(r + 1) * TILE_H, c * TILE_W:(c + 1) * TILE_W] = t
    if alerter.pending:
        p = min(alerter.pending, key=lambda p: p["deadline"])
        remain = max(0, p["deadline"] - now)
        msg = f"【警報】{p['cam']} {p['ev'].kind}:{remain:.1f} 秒後自動發出緊急通報,誤報請按 C 取消"
        color = (0, 0, 255)
    else:
        msg = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  監控中 {len(tiles)} 路   C 取消誤報  Q 離開"
        color = (200, 200, 200)
    return put_text(wall, [(msg, (10, rows * TILE_H + 10), color, FONT)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-line", action="store_true", help="不發 LINE")
    ap.add_argument("--headless", action="store_true", help="不開視窗")
    ap.add_argument("--seconds", type=float, default=0, help="執行指定秒數後結束(0=不限)")
    ap.add_argument("--serial", default="auto", help="警示盒序列埠:auto、none 或 COM3")
    ap.add_argument("--set", action="append", default=[], metavar="名稱=值", help="暫時修改門檻")
    args = ap.parse_args()
    if args.no_line:
        alerter_mod.LINE_ENABLED = False
    for item in args.set:
        name, value = tr.set_param(item)
        print(f"暫時設定 {name} = {value}")

    model = YOLO(MODEL_PATH)
    cams = [CameraState(FrameSource(cfg).start()) for cfg in SOURCES]
    alerter = Alerter()
    box = AlarmLink(args.serial)
    started = time.time()
    last_tiles = {}
    print(f"監控開始:{[c.source.name for c in cams]}", flush=True)

    while True:
        now = time.time()
        for cam in cams:
            fid, frame = cam.source.latest()
            if frame is None or fid == cam.last_frame_id:
                continue
            cam.last_frame_id = fid
            cam.dets = detect(model, frame)
            events, cam.people = cam.analyzer.analyze(cam.dets, now, frame.shape[0])
            for ev in events:
                cam.active[ev.kind] = (now, ev.level)
            tile = render_tile(cam, frame.copy(), now)
            last_tiles[cam.source.name] = tile
            if events:
                alerter.handle(cam.source.name, events, tile, now)
        alerter.tick(now)
        for msg in box.poll():
            if msg == "cancel":
                print("[警示盒] 保全按下取消鈕", flush=True)
                alerter.cancel_all(now)
        box.update(alerter, now)

        if not args.headless and last_tiles:
            tiles = [last_tiles.get(c.source.name, np.zeros((TILE_H, TILE_W, 3), np.uint8))
                     for c in cams]
            cv2.imshow("Public Safety Monitor", compose_wall(tiles, alerter, now))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("c"), ord("C")):
                alerter.cancel_all(now)
        else:
            time.sleep(0.01)
        if args.seconds and now - started >= args.seconds:
            break

    alerter.tick(time.time() + alerter_mod.CANCEL_WINDOW_SEC)  # 結束前把待送事件處理完
    box.send("S0N0")
    for c in cams:
        c.source.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
