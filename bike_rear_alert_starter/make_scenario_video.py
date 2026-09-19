"""產生「動作要求示意影片」：用動畫演出每種情境下，系統應該怎麼反應（教師說明用）。

畫面：左邊是朝後鏡頭（含車框、到達秒數、狀態列），右邊是俯視圖、ESP32 的 TFT、三色燈、
語音字幕與事件紀錄，下方是說明字幕。聲音使用 sd_card/01 的語音檔與蜂鳴器嗶聲。

警示等級、語音時機、TFT 內容都直接使用程式包的規則（AlertState、voice.Announcer、
voice.status_line、tft_labels.h），所以影片與程式的行為一致。車輛動作是事先安排好的模擬，
不是 YOLO 的實際辨識結果。

需要 ffmpeg（加上聲音與壓縮）。
用法：python make_scenario_video.py            輸出 output/scenario_demo.mp4
"""
import math
import os
import re
import shutil
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import voice

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
FPS = 30
W, H = 1280, 720
SR = 22050

FONT_R = "C:/Windows/Fonts/msjh.ttc"
FONT_B = "C:/Windows/Fonts/msjhbd.ttc"
FONT_M = "C:/Windows/Fonts/consolab.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


F14, F16, F18, F20, F22, F26, F34, F44 = (font(14), font(16), font(18, True), font(20), font(22),
                                           font(26, True), font(34, True), font(44, True))
FM18, FM22 = ImageFont.truetype(FONT_M, 18), ImageFont.truetype(FONT_M, 22)

# ---------- 設定（與 config.json 預設相同） ----------
TTC_WARN, TTC_DANGER = 4.0, 2.0
CONFIRM, HOLD, LOST = 2, 1.0, 0.8
DETECT_DT = 0.1
MIN_WIDTH_RATIO = 0.04
EST_DELAY = 0.4            # 追蹤開始後約 0.4 秒才有足夠的點估計 τ
OFFLINE_MS = 1.5

NAME_ZH = {"car": "汽車", "motorcycle": "機車", "truck": "大貨車", "bus": "公車"}
SIZE = {"car": (1.8, 1.5), "motorcycle": (0.8, 1.45), "truck": (2.5, 3.3), "bus": (2.5, 3.2)}

# ---------- 情境 ----------
# 車輛：(編號, 車種, 出現時間, 起始距離 m, 相對速度 m/s, 橫向位置 m, 消失時間)
VEHICLES = [
    (1, "motorcycle", 11.0, 32.0, 5.0, 1.4, None),
    (2, "car", 23.0, 20.0, 0.6, 2.3, 31.5),
    (3, "truck", 33.0, 62.0, 9.0, 2.7, None),
    (4, "car", 46.0, 42.0, 7.0, 2.5, None),
    (5, "motorcycle", 46.0, 18.0, 3.0, 1.3, None),
]
# 跟車的汽車在 28 秒後慢慢退後
FOLLOW_RECEDE = (2, 28.0, -2.0)

SEGMENTS = [
    (0.0, 5.0, "title", "", ""),
    (5.0, 11.0, "情境 0：系統啟動", "程式開始時說「警示系統啟動」。後方沒有來車：綠燈恆亮、TFT 顯示「安全」「後方無來車」。", ""),
    (11.0, 23.0, "情境 1：機車從後方逼近", "機車越來越近，車框變大 → 算出到達秒數 τ。τ < 4 秒：黃燈、說「後方機車」；τ < 2 秒：紅燈、說「危險，機車」。",
     "機車經過後，警示至少再維持 1 秒才解除。"),
    (23.0, 33.0, "情境 2：跟在後面、速度差不多的汽車", "車框大小幾乎不變 → τ 很大（遠大於 4 秒），所以不警示。",
     "停在路邊、比你慢、慢慢退後的車，也都不會警示。"),
    (33.0, 46.0, "情境 3：大貨車快速逼近", "大貨車比較大，在更遠的地方就被偵測到。τ < 4 秒說「後方大型車」，τ < 2 秒說「危險，大型車」。",
     "公車與貨車都算「大型車」。"),
    (46.0, 57.0, "情境 4：汽車和機車同時逼近", "兩台新的車同時進入注意 → 說「後方多台車」；兩種車同時危險 → 說「危險，注意」。",
     "同一台車只說一次；兩段語音至少間隔 1.5 秒。"),
    (57.0, 65.0, "情境 5：USB 線被拔掉", "ESP32 超過 1.5 秒沒收到電腦訊號 → 綠燈改成慢閃、TFT 顯示「未連線」，讓人知道系統沒在運作。",
     "重新接上後自動回到「安全」。"),
    (65.0, 71.0, "end", "", ""),
]
UNPLUG, REPLUG = 58.0, 62.5
TOTAL = 71.0

# ---------- 攝影機模型（朝後） ----------
CAM_X, CAM_Y, CAM_W, CAM_H = 16, 60, 820, 461
HORIZON = 0.40 * CAM_H
FOCAL = 0.9 * CAM_W
CAM_HEIGHT = 1.0
BIKE_SPEED = 5.0


def project(d, x, height=0.0):
    """距離 d（公尺）、橫向 x（公尺，正值＝畫面右邊＝騎士左側）、離地高度 → 畫面座標。"""
    u = CAM_W / 2 + FOCAL * x / d
    v = HORIZON + FOCAL * (CAM_HEIGHT - height) / d
    return u, v


def vehicle_distance(v, t):
    vid, kind, t0, d0, vr, lat, t_end = v
    if t < t0 or (t_end is not None and t > t_end):
        return None
    d = d0 - vr * (t - t0)
    if vid == FOLLOW_RECEDE[0] and t > FOLLOW_RECEDE[1]:
        d_at = d0 - vr * (FOLLOW_RECEDE[1] - t0)
        d = d_at - FOLLOW_RECEDE[2] * (t - FOLLOW_RECEDE[1])
    return d if d > 1.2 else None


def vehicle_speed(v, t):
    vid, kind, t0, d0, vr, lat, t_end = v
    if vid == FOLLOW_RECEDE[0] and t > FOLLOW_RECEDE[1]:
        return FOLLOW_RECEDE[2]
    return vr


def vehicle_box(v, d):
    _, kind, _, _, _, lat, _ = v
    w, h = SIZE[kind]
    x1, y2 = project(d, lat - w / 2, 0)
    x2, _ = project(d, lat + w / 2, 0)
    _, y1 = project(d, lat, h)
    return x1, y1, x2, y2


# ---------- 模擬狀態 ----------
class AlertState:
    """與 rear_alert.py 的 AlertState 相同的規則。"""

    def __init__(self, hold):
        self.hold, self.level, self.until, self.on = hold, 0, -1.0, False

    def update(self, want, now):
        event = None
        if want > 0:
            if not self.on:
                event = "alert_on"
            elif want > self.level:
                event = "escalate"
            self.on = True
            if want >= self.level or now >= self.until:
                self.level, self.until = want, now + self.hold
        elif self.on and now >= self.until:
            event = "alert_off"
            self.level, self.on = 0, False
        return event


def simulate():
    """逐一時間點計算：每台車的 τ 與等級、整體等級、語音、事件、傳給 ESP32 的狀態。"""
    state = AlertState(HOLD)
    ann = voice.Announcer(cooldown=1.5)
    tracks = {}          # 編號 → {"seen":, "hits":, "tau":, "level":, "last":}
    timeline = []        # 每 0.1 秒：(t, 整體等級, {編號: (tau, level)}, 顯示車種, 顯示 tau)
    voices = [(5.5, voice.CLIP_READY)]
    events = [(5.5, "語音：警示系統啟動")]
    shown_name, shown_tau = "", None
    n = int(TOTAL / DETECT_DT) + 1
    for i in range(n):
        t = round(i * DETECT_DT, 2)
        visible = {}
        for v in VEHICLES:
            d = vehicle_distance(v, t)
            if d is None:
                continue
            x1, y1, x2, y2 = vehicle_box(v, d)
            if (x2 - x1) / CAM_W < MIN_WIDTH_RATIO:
                continue
            visible[v[0]] = (v, d)
        for vid, (v, d) in visible.items():
            tr = tracks.setdefault(vid, {"seen": t, "hits": 0, "tau": None, "level": 0, "name": v[1]})
            tr["last"] = t
            vr = vehicle_speed(v, t)
            tr["tau"] = d / vr if (vr > 0 and t - tr["seen"] >= EST_DELAY) else None
        for vid in list(tracks):
            if t - tracks[vid]["last"] > LOST:
                del tracks[vid]
        want, worst = 0, None
        for vid, tr in tracks.items():
            tr["level"] = 0
            if vid not in visible or tr["tau"] is None or tr["tau"] >= TTC_WARN:
                tr["hits"] = 0
                continue
            tr["hits"] += 1
            if tr["hits"] < CONFIRM:
                continue
            tr["level"] = 2 if tr["tau"] < TTC_DANGER else 1
            if tr["level"] > want:
                want, worst = tr["level"], vid
        event = state.update(want, t)
        if worst is not None:
            shown_name, shown_tau = tracks[worst]["name"], tracks[worst]["tau"]
        elif not state.on:
            shown_name, shown_tau = "", None
        if event in ("alert_on", "escalate"):
            tr = tracks[worst]
            events.append((t, f"{'注意' if want == 1 else '危險'}：{NAME_ZH[tr['name']]} τ={tr['tau']:.1f} 秒"))
        elif event == "alert_off":
            events.append((t, "解除警示"))
        alerting = [(vid, tr["name"], tr["level"]) for vid, tr in tracks.items() if tr["level"] > 0]
        said = ann.update(t, alerting, state.level, event)
        if said:
            voices.append((t, said[0]))
            events.append((t, f"語音：{said[1]}"))
        per = {vid: (tr["tau"], tr["level"]) for vid, tr in tracks.items() if vid in visible}
        timeline.append((t, state.level, per, shown_name, shown_tau))
    events.append((UNPLUG, "USB 線拔除"))
    events.append((UNPLUG + OFFLINE_MS, "ESP32：未連線"))
    events.append((REPLUG, "USB 線接回"))
    events.sort()
    return timeline, voices, events


# ---------- TFT ----------
def load_labels():
    src = open(os.path.join(HERE, "esp32_rear_alert", "tft_labels.h"), encoding="utf-8").read()
    labels = {}
    pat = r"static const uint8_t (\w+)_DATA\[\] PROGMEM = \{(.*?)\};\s*static const Label \1 = \{(\d+), (\d+),"
    for m in re.finditer(pat, src, re.S):
        data = [int(x, 16) for x in re.findall(r"0x([0-9A-F]{2})", m.group(2))]
        labels[m.group(1)] = (int(m.group(3)), int(m.group(4)), data)
    return labels


LABELS = load_labels()


def rgb565(c):
    return ((c >> 11) & 0x1F) * 255 // 31, ((c >> 5) & 0x3F) * 255 // 63, (c & 0x1F) * 255 // 31


T_BLACK, T_WHITE, T_GREEN, T_YELLOW, T_RED, T_GRAY, T_RED_TX = map(
    rgb565, (0x0000, 0xFFFF, 0x0400, 0xFFE0, 0xC000, 0x4208, 0xF800))
_bitmap_cache = {}


def label_img(name, fg, bg):
    key = (name, fg, bg)
    if key not in _bitmap_cache:
        w, h, data = LABELS[name]
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        rb = (w + 7) // 8
        for j in range(h):
            for i in range(w):
                on = data[j * rb + i // 8] & (0x80 >> (i % 8))
                arr[j, i] = fg if on else bg
        _bitmap_cache[key] = Image.fromarray(arr)
    return _bitmap_cache[key]


def paste_label(img, name, cx, top, band, fg, bg):
    lb = label_img(name, fg, bg)
    img.paste(lb, (cx - lb.width // 2, top + (band - lb.height) // 2))


_tft_cache = {}


def tft_screen(level, code, tenths):
    key = (level, code, tenths)
    if key in _tft_cache:
        return _tft_cache[key]
    img = Image.new("RGB", (160, 128), T_BLACK)
    d = ImageDraw.Draw(img)
    bg, fg, lb = T_GRAY, T_WHITE, "LBL_OFFLINE"
    if level == 0:
        bg, lb = T_GREEN, "LBL_SAFE"
    elif level == 1:
        bg, fg, lb = T_YELLOW, T_BLACK, "LBL_CAUTION"
    elif level == 2:
        bg, lb = T_RED, "LBL_DANGER"
    d.rectangle([0, 0, 159, 39], fill=bg)
    paste_label(img, lb, 80, 0, 40, fg, bg)
    vfg = T_RED_TX if level == 2 else (T_YELLOW if level == 1 else T_WHITE)
    if level < 0:
        paste_label(img, "LBL_CHECK", 80, 44, 36, T_WHITE, T_BLACK)
    else:
        name = {"M": "LBL_MOTO", "C": "LBL_CAR", "B": "LBL_BIG"}.get(code if level > 0 else "N", "LBL_NONE")
        paste_label(img, name, 80, 44, 36, vfg if name != "LBL_NONE" else T_WHITE, T_BLACK)
    if level > 0:
        paste_label(img, "LBL_ARRIVE", 124, 96, 24, T_WHITE, T_BLACK)
        d.text((14, 93), f"{tenths // 10}.{tenths % 10}", font=ImageFont.truetype(FONT_M, 30), fill=T_WHITE)
    big = img.resize((320, 256), Image.NEAREST)
    _tft_cache[key] = big
    return big


# ---------- 畫面 ----------
SKY_TOP, SKY_BOTTOM = (125, 170, 215), (200, 220, 235)


def draw_scene(t, timeline_row):
    img = Image.new("RGB", (CAM_W, CAM_H), SKY_BOTTOM)
    d = ImageDraw.Draw(img)
    hz = int(HORIZON)
    for y in range(hz):
        k = y / max(1, hz - 1)
        d.line([(0, y), (CAM_W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(SKY_TOP, SKY_BOTTOM)))
    # 遠方建築
    for bx, bw, bh, col in ((20, 90, 60, (150, 150, 160)), (120, 70, 90, (170, 160, 150)), (200, 110, 50, (140, 150, 165)),
                            (560, 80, 70, (160, 150, 150)), (650, 120, 100, (150, 160, 170)), (780, 60, 55, (170, 165, 160))):
        d.rectangle([bx, hz - bh, bx + bw, hz], fill=col)
        for wy in range(hz - bh + 8, hz - 6, 14):
            for wx in range(bx + 8, bx + bw - 8, 16):
                d.rectangle([wx, wy, wx + 6, wy + 6], fill=(210, 220, 230))
    d.rectangle([0, hz, CAM_W, CAM_H], fill=(120, 150, 110))

    def ground_poly(xa, xb, d_near=2.0, d_far=400.0):
        return [project(d_near, xa), project(d_near, xb), project(d_far, xb), project(d_far, xa)]

    d.polygon(ground_poly(-6, -1.2), fill=(185, 180, 170))            # 人行道
    d.polygon(ground_poly(-1.2, 8.0), fill=(78, 80, 86))               # 路面
    d.polygon(ground_poly(8.0, 30), fill=(185, 180, 170))
    d.polygon(ground_poly(0.9, 0.97), fill=(235, 235, 235))            # 機慢車道線
    d.polygon(ground_poly(4.25, 4.33), fill=(230, 190, 40))            # 中央雙黃線
    d.polygon(ground_poly(4.40, 4.48), fill=(230, 190, 40))
    phase = (BIKE_SPEED * t) % 8.0
    for k in range(40):
        near = 2.0 + k * 8.0 - phase
        if near < 2.0:
            continue
        far = near + 3.5
        d.polygon([project(near, 2.55), project(near, 2.65), project(far, 2.65), project(far, 2.55)],
                  fill=(225, 225, 225))
    for k in range(60):                                                # 人行道磚縫
        dd = 2.0 + k * 3.0 - (BIKE_SPEED * t) % 3.0
        if dd >= 2.0:
            a, b = project(dd, -6), project(dd, -1.2)
            d.line([a, b], fill=(160, 155, 145), width=1)

    _, level, per, _, _ = timeline_row
    boxes = []
    for v in sorted(VEHICLES, key=lambda v: -(vehicle_distance(v, t) or 0)):
        dist = vehicle_distance(v, t)
        if dist is None:
            continue
        x1, y1, x2, y2 = vehicle_box(v, dist)
        draw_vehicle(d, v[1], x1, y1, x2, y2)
        if v[0] in per:
            boxes.append((v, dist, (x1, y1, x2, y2), per[v[0]]))

    zx = int(0.35 * CAM_W)
    d.line([(zx, 36), (zx, CAM_H)], fill=(220, 220, 220), width=1)
    d.rectangle([zx + 4, CAM_H - 30, zx + 172, CAM_H - 6], fill=(0, 0, 0))
    d.text((zx + 10, CAM_H - 29), "偵測範圍（zone_x）→", font=F16, fill=(255, 255, 255))
    colors = {0: (60, 180, 80), 1: (255, 200, 0), 2: (230, 40, 40)}
    for v, dist, (x1, y1, x2, y2), (tau, lv) in boxes:
        col = colors[lv]
        d.rectangle([x1, y1, x2, y2], outline=col, width=3)
        text = f"{v[1]} #{v[0]}" + (f"  {tau:.1f}s" if tau is not None and tau < 99 else "")
        ty = y1 - 24 if y1 > 64 else y1 + 4
        tw = d.textlength(text, font=FM18)
        d.rectangle([x1, ty, x1 + tw + 8, ty + 22], fill=(0, 0, 0))
        d.text((x1 + 4, ty + 1), text, font=FM18, fill=col)
    bar = {0: ((60, 150, 70), "SAFE"), 1: ((230, 180, 0), "CAUTION"), 2: ((200, 40, 40), "DANGER")}[level]
    d.rectangle([0, 0, CAM_W, 34], fill=bar[0])
    d.text((12, 5), f"{bar[1]}   t = {t:5.1f} s", font=FM22, fill=(255, 255, 255) if level != 1 else (0, 0, 0))
    d.text((CAM_W - 200, 8), "朝後鏡頭（模擬畫面）", font=F18, fill=(255, 255, 255) if level != 1 else (0, 0, 0))
    return img


def draw_vehicle(d, kind, x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    if w < 2:
        return
    if kind == "car":
        d.rounded_rectangle([x1, y1 + h * 0.38, x2, y2 - h * 0.06], radius=max(1, w * 0.08), fill=(190, 30, 40))
        d.polygon([(x1 + w * 0.14, y1 + h * 0.40), (x1 + w * 0.24, y1), (x2 - w * 0.24, y1), (x2 - w * 0.14, y1 + h * 0.40)],
                  fill=(170, 25, 35))
        d.polygon([(x1 + w * 0.2, y1 + h * 0.38), (x1 + w * 0.28, y1 + h * 0.07), (x2 - w * 0.28, y1 + h * 0.07),
                   (x2 - w * 0.2, y1 + h * 0.38)], fill=(150, 200, 230))
        r = w * 0.07
        for cx in (x1 + w * 0.14, x2 - w * 0.14):
            d.ellipse([cx - r, y1 + h * 0.52 - r * 0.7, cx + r, y1 + h * 0.52 + r * 0.7], fill=(255, 240, 170))
        d.rectangle([x1 + w * 0.36, y1 + h * 0.62, x2 - w * 0.36, y1 + h * 0.74], fill=(240, 240, 240))
        d.rectangle([x1 + w * 0.05, y2 - h * 0.1, x1 + w * 0.2, y2], fill=(25, 25, 25))
        d.rectangle([x2 - w * 0.2, y2 - h * 0.1, x2 - w * 0.05, y2], fill=(25, 25, 25))
    elif kind == "truck":
        d.rectangle([x1, y1, x2, y2 - h * 0.05], fill=(235, 235, 240))
        d.rectangle([x1 + w * 0.06, y1 + h * 0.08, x2 - w * 0.06, y1 + h * 0.42], fill=(120, 170, 210))
        d.rectangle([x1, y1 + h * 0.5, x2, y1 + h * 0.62], fill=(30, 80, 160))
        r = w * 0.06
        for cx in (x1 + w * 0.12, x2 - w * 0.12):
            d.ellipse([cx - r, y1 + h * 0.72 - r, cx + r, y1 + h * 0.72 + r], fill=(255, 240, 170))
        d.rectangle([x1 + w * 0.3, y1 + h * 0.66, x2 - w * 0.3, y1 + h * 0.84], fill=(70, 70, 75))
        d.rectangle([x1 - w * 0.02, y2 - h * 0.12, x2 + w * 0.02, y2 - h * 0.05], fill=(60, 60, 60))
        d.rectangle([x1 + w * 0.04, y2 - h * 0.06, x1 + w * 0.2, y2], fill=(20, 20, 20))
        d.rectangle([x2 - w * 0.2, y2 - h * 0.06, x2 - w * 0.04, y2], fill=(20, 20, 20))
    else:  # motorcycle
        cx = (x1 + x2) / 2
        d.ellipse([cx - w * 0.1, y2 - h * 0.34, cx + w * 0.1, y2], fill=(20, 20, 20))
        d.polygon([(cx - w * 0.3, y1 + h * 0.32), (cx + w * 0.3, y1 + h * 0.32), (cx + w * 0.22, y2 - h * 0.3),
                   (cx - w * 0.22, y2 - h * 0.3)], fill=(40, 60, 110))
        d.line([(x1, y1 + h * 0.42), (x2, y1 + h * 0.42)], fill=(30, 30, 30), width=max(1, int(w * 0.06)))
        d.ellipse([cx - w * 0.2, y1, cx + w * 0.2, y1 + h * 0.3], fill=(240, 200, 40))
        d.rectangle([cx - w * 0.14, y1 + h * 0.1, cx + w * 0.14, y1 + h * 0.18], fill=(40, 40, 50))
        r = w * 0.1
        d.ellipse([cx - r, y1 + h * 0.5 - r, cx + r, y1 + h * 0.5 + r], fill=(255, 245, 180))


def draw_topview(canvas, t, row, x0, y0, w, h):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=10, fill=(30, 41, 59))
    d.text((x0 + 12, y0 + 6), "俯視圖（行進方向 →）", font=F18, fill=(226, 232, 240))
    rx0, rx1 = x0 + 12, x0 + w - 12
    road_top, road_bot = y0 + 40, y0 + h - 30
    d.rectangle([rx0, road_top, rx1, road_bot], fill=(78, 80, 86))
    lane = road_top + (road_bot - road_top) * 0.62
    for xx in range(rx0, rx1, 18):
        d.line([(xx, lane), (xx + 9, lane)], fill=(225, 225, 225), width=2)
    bike_x = rx1 - 40
    scale = (bike_x - rx0 - 10) / 60.0          # 60 公尺
    by = road_bot - 16
    d.polygon([(bike_x - 4, by), (bike_x - 150, by - 34), (bike_x - 150, by + 10)], fill=(94, 234, 212))
    d.ellipse([bike_x - 8, by - 8, bike_x + 8, by + 8], fill=(253, 230, 138), outline=(180, 83, 9))
    d.text((bike_x + 10, by - 9), "騎士", font=F14, fill=(254, 243, 199))
    for m in (10, 20, 30, 40, 50):
        xx = bike_x - m * scale
        d.line([(xx, road_bot), (xx, road_bot + 5)], fill=(148, 163, 184))
        d.text((xx - 14, road_bot + 6), f"{m}m", font=F14, fill=(148, 163, 184))
    _, level, per, _, _ = row
    for v in VEHICLES:
        dist = vehicle_distance(v, t)
        if dist is None or dist > 60:
            continue
        vid, kind = v[0], v[1]
        xx = bike_x - dist * scale
        yy = road_top + (lane - road_top) * (0.35 if kind == "motorcycle" else 0.6)
        ln, wd = {"car": (16, 9), "truck": (26, 11), "motorcycle": (10, 5)}.get(kind, (16, 9))
        lv = per.get(vid, (None, 0))[1]
        col = {0: (203, 213, 225), 1: (250, 204, 21), 2: (248, 113, 113)}[lv]
        d.rectangle([xx - ln, yy - wd / 2, xx, yy + wd / 2], fill=col)
        tau = per.get(vid, (None, 0))[0]
        txt = f"{dist:4.1f}m" + (f" τ{tau:.1f}" if tau is not None and tau < 99 else "")
        d.text((xx - ln, yy - wd / 2 - 18), txt, font=F14, fill=(241, 245, 249))


def draw_panel(canvas, t, row, esp_status, esp_level, voice_text, beep_on, recent, plugged=True):
    d = ImageDraw.Draw(canvas)
    x0, y0 = 852, 262
    d.rounded_rectangle([x0, y0, W - 16, 604], radius=10, fill=(30, 41, 59))
    d.text((x0 + 12, y0 + 6), "ESP32 裝置（TFT、三色燈、蜂鳴器、語音）", font=F18, fill=(226, 232, 240))
    level, code, tenths = esp_status
    canvas.paste(tft_screen(level, code, tenths), (x0 + 46, y0 + 36))
    d.rectangle([x0 + 45, y0 + 35, x0 + 366, y0 + 292], outline=(100, 116, 139))
    ms = int(t * 1000)
    if esp_level == 0:
        g, yl, r = True, False, False
    elif esp_level == 1:
        g, yl, r = False, (ms // 250) % 2 == 1, False
    elif esp_level == 2:
        g, yl, r = False, False, (ms // 100) % 2 == 1
    else:
        g, yl, r = (ms % 2000) < 150, False, False
    ly = y0 + 308
    for i, (on, oncol, offcol, name) in enumerate(((g, (34, 197, 94), (20, 60, 35), "綠"), (yl, (250, 204, 21), (70, 60, 15), "黃"),
                                                   (r, (239, 68, 68), (70, 20, 20), "紅"))):
        cx = x0 + 70 + i * 62
        d.ellipse([cx - 16, ly - 16, cx + 16, ly + 16], fill=oncol if on else offcol, outline=(148, 163, 184))
        d.text((cx - 7, ly + 17), name, font=F14, fill=(203, 213, 225))
    bx = x0 + 270
    if not plugged:
        d.rounded_rectangle([bx - 14, ly - 16, W - 26, ly + 16], radius=8, fill=(185, 28, 28))
        d.text((bx - 2, ly - 12), "USB 已拔除", font=F18, fill=(255, 255, 255))
    else:
        d.text((bx, ly - 12), "蜂鳴器", font=F16, fill=(203, 213, 225))
    if beep_on:
        for k in range(3):
            d.arc([bx + 58 - k * 6, ly - 14 - k * 6, bx + 78 + k * 6, ly + 6 + k * 6], -45, 45, fill=(250, 204, 21), width=2)
    # 語音
    vy = 612
    d.rounded_rectangle([x0, vy, W - 16, vy + 42], radius=10,
                        fill=(8, 80, 70) if voice_text else (30, 41, 59))
    d.polygon([(x0 + 14, vy + 15), (x0 + 22, vy + 15), (x0 + 32, vy + 7), (x0 + 32, vy + 35), (x0 + 22, vy + 27),
               (x0 + 14, vy + 27)], fill=(240, 253, 250) if voice_text else (100, 116, 139))
    d.text((x0 + 44, vy + 7), f"語音：「{voice_text}」" if voice_text else "語音：（無）", font=F22,
           fill=(240, 253, 250) if voice_text else (148, 163, 184))
    # 事件紀錄
    ey = 662
    d.text((x0, ey), "紀錄：", font=F16, fill=(148, 163, 184))
    for i, (et, text) in enumerate(recent[-2:]):
        d.text((x0 + 52, ey + i * 22 - 2), f"{et:5.1f}s  {text}", font=F16, fill=(226, 232, 240))


NO_LINE_START = "，。；、：」）！？"


def wrap(d, text, fnt, width):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=fnt) > width and ch not in NO_LINE_START:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_caption(canvas, seg, t):
    d = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = 16, 530, 836, 704
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(30, 41, 59))
    _, _, title, text, note = seg
    d.text((x0 + 16, y0 + 10), title, font=F26, fill=(253, 224, 71))
    yy = y0 + 50
    for line in wrap(d, text, F22, x1 - x0 - 32):
        d.text((x0 + 16, yy), line, font=F22, fill=(241, 245, 249))
        yy += 32
    if note:
        for line in wrap(d, note, F20, x1 - x0 - 32):
            d.text((x0 + 16, yy + 2), line, font=F20, fill=(148, 197, 255))
            yy += 28


def title_card(kind):
    img = Image.new("RGB", (W, H), (15, 23, 42))
    d = ImageDraw.Draw(img)
    if kind == "title":
        d.text((80, 90), "自行車「後方來車」警示", font=F44, fill=(255, 255, 255))
        d.text((80, 160), "動作要求示意（模擬動畫）", font=F34, fill=(253, 224, 71))
        items = ["左邊：朝後鏡頭看到的畫面，車框旁是估計的到達秒數 τ",
                 "右上：俯視圖，顯示後方車輛的距離",
                 "右下：ESP32 的 TFT、三色燈、蜂鳴器與語音",
                 "黃燈＝注意（τ < 4 秒）　紅燈＝危險（τ < 2 秒）　綠燈慢閃＝未連線",
                 "車輛動作是事先安排的模擬，警示與語音規則和程式包相同"]
        for i, s in enumerate(items):
            d.text((96, 260 + i * 56), "・" + s, font=F26 if i < 4 else font(24), fill=(226, 232, 240))
    else:
        d.text((80, 80), "重點整理", font=F44, fill=(255, 255, 255))
        items = ["車框越變越大 → 算出到達秒數 τ；τ < 4 秒注意、τ < 2 秒危險",
                 "一台車第一次進入注意時說出車種，同一台車只說一次",
                 "升到危險時說「危險，＋車種」；兩種車同時危險說「危險，注意」",
                 "跟車、慢車、遠離的車不警示；警示解除前至少維持 1 秒",
                 "系統沒在運作時一定看得出來：綠燈慢閃、TFT 顯示未連線",
                 "請用錄好的影片或桌上模型測試，不要邊騎車邊看螢幕"]
        for i, s in enumerate(items):
            d.text((96, 190 + i * 70), "・" + s, font=F26, fill=(226, 232, 240) if i < 5 else (252, 165, 165))
    return img


# ---------- 聲音 ----------
def read_clip(n):
    path = os.path.join(HERE, "sd_card", "01", f"{n:03d}.wav")
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    return data


def build_audio(voices, esp_levels, quiet):
    total = int(TOTAL * SR)
    audio = np.zeros(total, dtype=np.float32)
    ts = np.arange(total) / SR
    ms = (ts * 1000).astype(np.int64)
    frame = np.minimum((ts * FPS).astype(int), len(esp_levels) - 1)
    lv = np.array(esp_levels)[frame]
    qt = np.array(quiet)[frame]
    on = ((lv == 1) & (ms % 1000 < 60)) | ((lv == 2) & ((ms // 100) % 2 == 1))
    on &= ~qt
    tone = 0.10 * np.sign(np.sin(2 * math.pi * 2300 * ts))
    audio += tone * on
    lengths = {}
    for t, clip in voices:
        data = read_clip(clip)
        lengths[(t, clip)] = len(data) / SR
        i = int(t * SR)
        end = min(total, i + len(data))
        audio[i:end] = audio[i:end] * 0.2 + data[:end - i] * 0.9    # 新語音會蓋過舊的（DFPlayer 行為）
        # 被打斷的舊語音：從這裡之後不再播放
    audio = np.clip(audio, -1, 1)
    return (audio * 32767).astype(np.int16), lengths


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    timeline, voices, events = simulate()
    clip_len = {n: len(read_clip(n)) / SR for n in voice.CLIPS}

    # 語音播放區間（新的會打斷舊的）
    spans = []
    for i, (t, clip) in enumerate(voices):
        end = t + clip_len[clip]
        if i + 1 < len(voices):
            end = min(end, voices[i + 1][0])
        spans.append((t, end, voice.CLIPS[clip]))

    nframes = int(TOTAL * FPS)
    esp_levels, quiet = [], []
    last_sent, esp_status, esp_level = -1.0, (0, "N", 0), -1
    tmp_video = os.path.join(OUT_DIR, "_scenario_video_only.mp4")
    ff = shutil.which("ffmpeg")
    if not ff:
        raise SystemExit("找不到 ffmpeg，請先安裝（例如 winget install Gyan.FFmpeg）")
    proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                             "-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)
    cards = {k: title_card(k) for k in ("title", "end")}
    for f in range(nframes):
        t = f / FPS
        row = timeline[min(len(timeline) - 1, int(round(t / DETECT_DT)))]
        # 電腦每 0.2 秒送一次狀態；拔線期間不送
        plugged = not (UNPLUG <= t < REPLUG)
        if plugged and t - last_sent >= 0.2 - 1e-6:
            last_sent = t
            line = voice.status_line(row[1], row[3], row[4])
            esp_status = (int(line[1]), line[2], int(line[3:]))
            esp_level = esp_status[0]
        if t - last_sent > OFFLINE_MS or t < 0.3:
            esp_level = -1
            esp_status = (-1, "N", 0)
        seg = next(s for s in SEGMENTS if s[0] <= t < s[1])
        speaking = next((txt for a, b, txt in spans if a <= t < b), "")
        q = any(a <= t < a + 1.2 for a, _, _ in spans)
        esp_levels.append(esp_level)
        quiet.append(q)
        if seg[2] in cards:
            frame = cards[seg[2]]
        else:
            frame = Image.new("RGB", (W, H), (15, 23, 42))
            dd = ImageDraw.Draw(frame)
            dd.text((16, 14), "自行車「後方來車」警示・動作要求示意（模擬動畫）", font=F26, fill=(255, 255, 255))
            frame.paste(draw_scene(t, row), (CAM_X, CAM_Y))
            draw_topview(frame, t, row, 852, 60, W - 16 - 852, 190)
            ms = int(t * 1000)
            beep = ((esp_level == 1 and ms % 1000 < 60) or (esp_level == 2 and (ms // 100) % 2 == 1)) and not q
            recent = [e for e in events if e[0] <= t]
            draw_panel(frame, t, row, esp_status, esp_level, speaking, beep, recent, plugged)
            draw_caption(frame, seg, t)
        proc.stdin.write(frame.tobytes())
        if f % (FPS * 10) == 0:
            print(f"  產生畫面 {t:4.0f} / {TOTAL:.0f} 秒")
    proc.stdin.close()
    proc.wait()

    audio, _ = build_audio(voices, esp_levels, quiet)
    wav_path = os.path.join(OUT_DIR, "_scenario_audio.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(audio.tobytes())

    out = os.path.join(OUT_DIR, "scenario_demo.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", tmp_video, "-i", wav_path, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "96k", "-movflags", "+faststart", "-shortest", out], check=True)
    os.remove(tmp_video)
    os.remove(wav_path)
    print("完成：", out)
    print("\n語音時間表：")
    for t, clip in voices:
        print(f"  {t:5.1f} 秒  {voice.CLIPS[clip]}")
    print("\n事件：")
    for t, e in events:
        print(f"  {t:5.1f} 秒  {e}")


if __name__ == "__main__":
    main()
