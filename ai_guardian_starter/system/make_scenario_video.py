"""
產生「動作要求示意影片」：用動畫演出每種情境下，系統應該怎麼反應（教師說明用）。

畫面：左邊是監視畫面（人物、偵測框、持械確認進度），右邊是現場警示盒（TFT、三色燈、蜂鳴器、
取消鈕）、手機 LINE 與事件紀錄，下方是說明字幕。聲音是警示盒的嗶聲與 LINE 提示音。

人物動作與偵測結果來自 demo_scenes.py（和練習資料相同）；判斷規則、通報流程、警示盒狀態
直接使用 threat_rules.py、alerter.py、alarm_link.py，所以影片和程式的行為一致。
為了讓每個情境都看得到完整流程，每個情境當作不同的監視點（冷卻時間分開計算）。

需要 ffmpeg。
用法：python make_scenario_video.py        輸出 output/scenario_demo.mp4 與 output/tft_preview.png
"""
import re
import shutil
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import alarm_link
import alerter as alerter_mod
import demo_scenes as ds
import detlog
import threat_rules as tr

FPS = 30
W, H = 1280, 720
SR = 22050
CAM_X, CAM_Y, CAM_W, CAM_H = 16, 58, 800, 450
S = CAM_W / ds.W                                   # 演練座標 → 畫面座標
PANEL_X = 832

FONT_R = "C:/Windows/Fonts/msjh.ttc"
FONT_B = "C:/Windows/Fonts/msjhbd.ttc"
FONT_M = "C:/Windows/Fonts/consolab.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


F13, F15, F17, F19B, F22, F26B, F34B = (font(13), font(15), font(17), font(19, True), font(22),
                                        font(26, True), font(34, True))
FM14, FM40 = ImageFont.truetype(FONT_M, 14), ImageFont.truetype(FONT_M, 40)

# ---------- 片段：(演練開始秒, 結束秒, 標題, 說明) ----------
CANCEL_AT = 35.5            # 情境 2：保全按下取消鈕的時間
UNPLUG_AT = 175.0           # 最後一段：拔掉警示盒的 USB 線
SEGMENTS = [
    ("title", 4.0),
    (2.0, 8.0, "情境 0：平常的穿堂", "只有人走動，綠燈恆亮，TFT 顯示「監控中」。"),
    (10.0, 26.0, "情境 1：有人拿起剪刀並持續拿著",
     "剪刀的框和人的框重疊＝手持；持續 0.6 秒才成立警報。警示盒紅燈快閃、嗶聲，倒數 5 秒；沒人取消就發出 LINE 緊急通報。"),
    (29.0, 41.0, "情境 2：剪刀在桌上，有人從桌旁走過",
     "人框碰到桌上的剪刀，被誤判為手持（誤報）。保全看畫面確認沒事，5 秒內按下取消鈕 → 標記為誤報，不發 LINE。"),
    (41.0, 49.0, "情境 3：剪刀只晃一下、零星誤判",
     "只出現不到 0.6 秒，進度條沒跑滿就不警報。AI 偶爾認錯一格也不會觸發。"),
    (50.0, 62.0, "情境 4：有人倒地超過 3 秒",
     "人框「寬比高大」持續 3 秒 → 中風險：黃燈、TFT「注意」，直接發 LINE（不需要倒數）。"),
    (66.0, 72.0, "情境 5：蹲下綁鞋帶 1.5 秒", "框暫時變寬，但不到 3 秒，不警示。"),
    (81.0, 92.0, "情境 6：人群快速跑過",
     "3 人以上同時快速移動超過 1 秒 → 高風險，和持械一樣倒數 5 秒後通報。"),
    (110.0, 122.0, "情境 8：16 人聚在一起",
     "人數達 15 人並持續 5 秒 → 低風險：黃燈、TFT「注意」，只寫入紀錄，不發 LINE。"),
    (150.0, 160.0, "情境 10：剪刀離鏡頭遠，信心度偏低",
     "信心度只有 0.27，低於門檻 0.35 → 漏報。門檻調低會抓到，但誤報也會變多：要用數據找平衡。"),
    (166.0, 173.0, "情境 11：手機被認成刀子（信心度 0.28）",
     "預設門檻下不警示。如果把門檻調到 0.25，這裡就會變成誤報。"),
    (173.0, 180.0, "情境 12：警示盒的 USB 線被拔掉",
     "超過 1.5 秒沒收到電腦訊號 → 綠燈慢閃、TFT「未連線」：壞掉時一定要看得出來。"),
    ("end", 6.0),
]

KIND_OF_CODE = {v: k for k, v in alarm_link.KIND_CODE.items()}
C565 = {"green": (0, 128, 0), "yellow": (255, 255, 0), "red": (198, 0, 0), "red_tx": (255, 0, 0),
        "blue": (41, 77, 123), "gray": (66, 65, 66), "black": (0, 0, 0), "white": (255, 255, 255)}


# ---------- 模擬：規則 + 通報 + 警示盒 ----------
def simulate():
    frames = ds.build_frames()
    tmp = Path(tempfile.mkdtemp())
    alerter_mod.EVENT_DIR = tmp
    alerter_mod.LINE_ENABLED = False
    alerter_mod._beep = lambda: None
    messages = []
    alerter_mod.Alerter._send = lambda self, text: messages.append((self._now, text))
    alerter = alerter_mod.Alerter()
    analyzer = tr.ThreatAnalyzer()
    dummy = np.zeros((8, 8, 3), np.uint8)
    rows, log = [], []
    cancelled = False
    for t, h, _w, dets in frames:
        alerter._now = t
        events, people = analyzer.analyze(dets, t, h)
        cam = next(f"情境{i}" for i, sc_ in enumerate(ds.SCENES) if sc_[0] <= t < sc_[1] or i == len(ds.SCENES) - 1)
        before = len(alerter.pending)
        if events:
            n_msg = len(messages)
            n_sent = len(alerter.last_sent)
            alerter.handle(cam, events, dummy, t)
            if len(alerter.pending) > before:
                log.append((t, f"{alerter.pending[-1]['ev'].kind}→倒數 5 秒"))
            elif len(messages) > n_msg:
                log.append((t, "倒地→直接發 LINE"))
            elif len(alerter.last_sent) > n_sent:
                log.append((t, "聚集→只記錄"))
        if not cancelled and t >= CANCEL_AT and alerter.pending:
            cancelled = True
            log.append((t, "保全取消→記為誤報"))
            alerter.cancel_all(t)
        n_msg = len(messages)
        alerter.tick(t)
        for _, text in messages[n_msg:]:
            log.append((t, "倒數結束→發 LINE"))
        flag = analyzer.weapon_flag
        progress = 0.0
        if flag.since is not None:
            progress = min(1.0, (flag.last_true - flag.since) / flag.sustain_sec)
        rows.append({"t": t, "dets": dets, "events": events, "people": people, "progress": progress,
                     "state": alarm_link.compute_state(alerter, t)})
    shutil.rmtree(tmp, ignore_errors=True)
    return rows, messages, log


# ---------- TFT（依韌體版面繪製）----------
def load_labels():
    text = (Path(__file__).parent / "esp32_guard_alarm" / "tft_labels.h").read_text(encoding="utf-8")
    labels = {}
    for m in re.finditer(r"static const uint8_t (\w+)_DATA\[\] PROGMEM = \{(.*?)\};", text, re.S):
        labels[m.group(1)] = [int(x, 16) for x in re.findall(r"0x([0-9A-F]{2})", m.group(2))]
    sizes = {m.group(1): (int(m.group(2)), int(m.group(3)))
             for m in re.finditer(r"static const Label (\w+) = \{(\d+), (\d+),", text)}
    out = {}
    for name, data in labels.items():
        w, h = sizes[name]
        bits = np.unpackbits(np.array(data, np.uint8)).reshape(h, -1)[:, :w]
        out[name] = bits.astype(bool)
    return out


LABELS = None


def paste_label(img, name, cx, top, band, fg, bg):
    mask = LABELS[name]
    h, w = mask.shape
    x, y = cx - w // 2, top + (band - h) // 2
    arr = np.array(img)
    region = arr[y:y + h, x:x + w]
    region[mask] = fg
    region[~mask] = bg
    return Image.fromarray(arr)


def tft_screen(state, code, seconds):
    img = Image.new("RGB", (160, 128), C565["black"])
    bg, fg, lb = C565["gray"], C565["white"], "LBL_OFF"
    if state == 0:
        bg, lb = C565["green"], "LBL_S0"
    elif state == 1:
        bg, fg, lb = C565["yellow"], C565["black"], "LBL_S1"
    elif state == 2:
        bg, lb = C565["red"], "LBL_S2"
    elif state == 3:
        bg, lb = C565["red"], "LBL_S3"
    elif state == 4:
        bg, lb = C565["blue"], "LBL_S4"
    ImageDraw.Draw(img).rectangle((0, 0, 159, 37), fill=bg)
    img = paste_label(img, lb, 80, 0, 38, fg, bg)
    if state >= 0:
        kfg = C565["white"]
        if state == 1:
            kfg = C565["yellow"]
        if state in (2, 3):
            kfg = C565["red_tx"]
        kname = {"W": "LBL_KW", "R": "LBL_KR", "F": "LBL_KF", "C": "LBL_KC"}.get(code if state > 0 else "N", "LBL_KN")
        img = paste_label(img, kname, 80, 40, 34, kfg, C565["black"])
    white, black = C565["white"], C565["black"]
    if state == -1:
        img = paste_label(img, "LBL_CHECK", 80, 76, 52, white, black)
    elif state == 1:
        img = paste_label(img, "LBL_WATCH", 80, 76, 52, white, black)
    elif state == 2:
        img = paste_label(img, "LBL_AFTER", 104, 78, 30, white, black)
        img = paste_label(img, "LBL_PRESS", 80, 108, 20, C565["yellow"], black)
        ImageDraw.Draw(img).text((22, 76), str(seconds), font=FM40, fill=white)
    elif state == 3:
        img = paste_label(img, "LBL_SENT", 80, 76, 52, white, black)
    elif state == 4:
        img = paste_label(img, "LBL_FALSE", 80, 76, 52, white, black)
    return img


def box_outputs(state, t, click):
    """(綠, 黃, 紅, 蜂鳴器) 依韌體的燈號規則。"""
    ms = int(t * 1000)
    if state == 0:
        g, y, r, b = True, False, False, False
    elif state == 1:
        g, y, r, b = False, True, False, False
    elif state == 2:
        on = (ms // 100) % 2 == 1
        g, y, r, b = False, False, on, on
    elif state == 3:
        g, y, r, b = False, False, True, ms % 2000 < 80
    elif state == 4:
        g, y, r, b = (ms // 250) % 2 == 1, False, False, False
    else:
        g, y, r, b = ms % 2000 < 150, False, False, False
    return g, y, r, b or click


# ---------- 監視畫面 ----------
SHIRTS = [(59, 130, 246), (234, 88, 12), (22, 163, 74), (147, 51, 234), (219, 39, 119), (14, 116, 144),
          (202, 138, 4), (100, 116, 139)]


def shirt(aid):
    return SHIRTS[zlib.crc32(aid.encode()) % len(SHIRTS)]


def sc(v):
    return v * S


def draw_background(d):
    d.rectangle((0, 0, CAM_W, sc(380)), fill=(214, 211, 201))
    d.rectangle((0, sc(380), CAM_W, CAM_H), fill=(176, 170, 158))
    for i in range(-6, 16):
        d.line((sc(640) + i * 60, sc(380), sc(640) + i * 160, CAM_H), fill=(160, 154, 142), width=1)
    for yy in (430, 500, 590, 700):
        d.line((0, sc(yy), CAM_W, sc(yy)), fill=(160, 154, 142), width=1)
    d.rectangle((sc(80), sc(130), sc(260), sc(380)), fill=(120, 94, 70))          # 門
    d.rectangle((sc(90), sc(140), sc(250), sc(370)), outline=(90, 70, 52), width=2)
    d.rectangle((sc(520), sc(90), sc(760), sc(200)), fill=(236, 240, 244), outline=(120, 130, 140))
    d.text((sc(548), sc(122)), "公 告 欄", font=F15, fill=(71, 85, 105))
    d.rectangle((sc(930), sc(515), sc(1110), sc(535)), fill=(146, 104, 62))       # 桌子
    d.rectangle((sc(945), sc(535), sc(958), sc(600)), fill=(110, 78, 46))
    d.rectangle((sc(1082), sc(535), sc(1095), sc(600)), fill=(110, 78, 46))


def draw_object(d, cls, box, phone=False):
    x1, y1, x2, y2 = (sc(v) for v in box)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if phone:
        d.rounded_rectangle((cx - 4, cy - 8, cx + 4, cy + 8), 2, fill=(30, 41, 59))
    elif cls == 76:
        d.ellipse((x1, cy - 1, x1 + 7, cy + 6), outline=(220, 38, 38), width=2)
        d.ellipse((x1, cy - 8, x1 + 7, cy - 1), outline=(220, 38, 38), width=2)
        d.line((x1 + 6, cy + 1, x2, cy - 5), fill=(148, 163, 184), width=2)
        d.line((x1 + 6, cy - 3, x2, cy + 3), fill=(148, 163, 184), width=2)
    else:
        d.polygon([(cx - 2, cy + 7), (cx + 10, cy - 9), (cx + 3, cy + 8)], fill=(203, 213, 225))
        d.rectangle((cx - 6, cy + 5, cx, cy + 11), fill=(40, 30, 20))


def draw_person(d, a, t):
    x1, y1, x2, y2 = (sc(v) for v in ds.person_box(a["x"], a["foot"], a["pose"]))
    w, h = x2 - x1, y2 - y1
    color = shirt(a["id"])
    skin, pants = (240, 200, 160), (51, 65, 85)
    if a["pose"] == "lie":
        r = h * 0.35
        d.ellipse((x1, y2 - 2 * r - 2, x1 + 2 * r, y2 - 2), fill=skin)
        d.rounded_rectangle((x1 + 2 * r, y2 - h * 0.75, x1 + w * 0.62, y2 - 2), 4, fill=color)
        d.rounded_rectangle((x1 + w * 0.6, y2 - h * 0.55, x2, y2 - 4), 3, fill=pants)
        return
    if a["pose"] == "bend":
        r = w * 0.16
        d.ellipse((x1 + w * 0.55, y1, x1 + w * 0.55 + 2 * r, y1 + 2 * r), fill=skin)
        d.polygon([(x1 + w * 0.15, y2 - h * 0.35), (x1 + w * 0.6, y1 + r), (x1 + w * 0.75, y1 + 2.2 * r),
                   (x1 + w * 0.3, y2 - h * 0.2)], fill=color)
        d.rounded_rectangle((x1 + w * 0.1, y2 - h * 0.35, x1 + w * 0.45, y2), 3, fill=pants)
        return
    r = w * 0.3
    cx = (x1 + x2) / 2
    d.ellipse((cx - r, y1, cx + r, y1 + 2 * r), fill=skin)
    body_top, body_bot = y1 + 2 * r + 1, y1 + h * 0.6
    d.rounded_rectangle((x1 + w * 0.12, body_top, x2 - w * 0.12, body_bot), 4, fill=color)
    swing = 0
    if a["run"]:
        swing = w * 0.45 * np.sin(t * 18)
    elif a["id"].startswith(("P", "B", "K")):
        swing = w * 0.15 * np.sin(t * 8)
    d.line((cx - w * 0.15, body_bot, cx - w * 0.15 - swing, y2), fill=pants, width=max(3, int(w * 0.22)))
    d.line((cx + w * 0.15, body_bot, cx + w * 0.15 + swing, y2), fill=pants, width=max(3, int(w * 0.22)))
    hand_y = y1 + h * 0.45
    arm_w = max(2, int(w * 0.14))
    if a["hold"]:
        d.line((x2 - w * 0.15, body_top + 4, x2 + 2, hand_y), fill=skin, width=arm_w)
        draw_object(d, a["hold"][0], ds.hand_box(ds.person_box(a["x"], a["foot"], a["pose"])), a.get("phone"))
    else:
        d.line((x2 - w * 0.15, body_top + 4, x2 - w * 0.05 + swing * 0.5, hand_y + h * 0.05), fill=skin, width=arm_w)
    d.line((x1 + w * 0.15, body_top + 4, x1 + w * 0.05 - swing * 0.5, hand_y + h * 0.05), fill=skin, width=arm_w)


def draw_camera(t, row):
    img = Image.new("RGB", (CAM_W, CAM_H))
    d = ImageDraw.Draw(img)
    draw_background(d)
    if ds.DESK_SCISSORS[0] <= t < ds.DESK_SCISSORS[1]:
        draw_object(d, 76, ds.DESK_BOX)
    for a in sorted(ds.actors_at(t), key=lambda a: a["foot"]):
        draw_person(d, a, t)
    weapons = tr.weapon_classes()
    for det in row["dets"]:
        x1, y1, x2, y2 = (sc(v) for v in det.box)
        if det.cls == tr.PERSON:
            d.rectangle((x1, y1, x2, y2), outline=(34, 197, 94), width=2)
        elif det.cls in weapons and det.conf >= tr.WEAPON_CONF:
            d.rectangle((x1, y1, x2, y2), outline=(239, 68, 68), width=3)
            d.text((x1, y1 - 17), f"{weapons[det.cls][:2]} {det.conf:.2f}", font=F13, fill=(255, 255, 255),
                   stroke_width=2, stroke_fill=(185, 28, 28))
        else:
            d.rectangle((x1, y1, x2, y2), outline=(251, 191, 36), width=1)
            d.text((x1, y2 + 1), f"{det.conf:.2f}", font=F13, fill=(255, 255, 255), stroke_width=2,
                   stroke_fill=(146, 64, 14))
    kinds = "、".join(f"{e.kind}（{e.level}）" for e in row["events"])
    d.rectangle((0, 0, CAM_W, 30), fill=(15, 23, 42))
    d.text((10, 4), f"{'【警示】' + kinds if kinds else '監控中'}　人數 {row['people']}",
           font=F17, fill=(252, 165, 165) if kinds else (226, 232, 240))
    d.text((CAM_W - 150, 7), f"演練時間 {row['t']:5.1f} 秒", font=F13, fill=(148, 163, 184))
    # 持械確認進度條
    d.rectangle((10, CAM_H - 30, 250, CAM_H - 8), fill=(15, 23, 42))
    d.rectangle((14, CAM_H - 25, 14 + 150 * row["progress"], CAM_H - 13), fill=(239, 68, 68))
    d.rectangle((14, CAM_H - 25, 164, CAM_H - 13), outline=(148, 163, 184))
    d.text((172, CAM_H - 28), "持械確認", font=F13, fill=(226, 232, 240))
    if row["events"]:
        d.rectangle((0, 0, CAM_W - 1, CAM_H - 1), outline=(239, 68, 68), width=6)
    return img


def draw_legend(d):
    y = CAM_Y + CAM_H + 16
    items = [((34, 197, 94), "人"), ((239, 68, 68), "危險物品（信心度達 0.35）"), ((251, 191, 36), "信心度不足，不採用")]
    x = CAM_X
    for col, text in items:
        d.rectangle((x, y + 4, x + 22, y + 20), outline=col, width=3)
        d.text((x + 30, y), text, font=F17, fill=(226, 232, 240))
        x += 60 + F17.getlength(text)
    d.text((CAM_X, y + 32), "紅色進度條跑滿（0.6 秒）才成立持械警報；事件紀錄的數字是演練時間（秒）。",
           font=F17, fill=(148, 163, 184))


# ---------- 右側面板 ----------
def draw_panel(canvas, t, state, plugged, click, messages, log):
    d = ImageDraw.Draw(canvas)
    x0 = PANEL_X
    d.rounded_rectangle((x0, 58, W - 16, 330), 10, fill=(30, 41, 59), outline=(71, 85, 105))
    d.text((x0 + 14, 64), "現場警示盒（ESP32）", font=F19B, fill=(255, 255, 255))
    st = state if plugged or state == -1 else state
    screen = tft_screen(st[0], alarm_link.KIND_CODE.get(st[1], "N"), st[2]).resize((256, 205), Image.NEAREST)
    canvas.paste(screen, (x0 + 14, 96))
    d.rectangle((x0 + 12, 94, x0 + 271, 302), outline=(148, 163, 184), width=2)
    g, y, r, b = box_outputs(st[0], t, click)
    for i, (on, col, name) in enumerate([(g, (34, 197, 94), "綠"), (y, (250, 204, 21), "黃"), (r, (239, 68, 68), "紅")]):
        cy = 118 + i * 50
        fill = col if on else tuple(int(c * 0.25) for c in col)
        d.ellipse((x0 + 300, cy - 15, x0 + 330, cy + 15), fill=fill, outline=(148, 163, 184))
        d.text((x0 + 338, cy - 10), name, font=F15, fill=(226, 232, 240))
    d.text((x0 + 300, 262), "嗶！" if b else "　", font=F19B, fill=(250, 204, 21))
    d.ellipse((x0 + 360, 250, x0 + 410, 300), fill=(254, 202, 202) if click else (220, 38, 38),
              outline=(255, 255, 255), width=3 if click else 1)
    d.text((x0 + 358, 304), "取消鈕", font=F13, fill=(226, 232, 240))
    if not plugged:
        d.text((x0 + 14, 306), "USB 線已拔除", font=F15, fill=(252, 165, 165))
    elif click:
        d.text((x0 + 14, 306), "保全按下取消鈕", font=F15, fill=(253, 224, 71))

    # 手機 LINE
    d.rounded_rectangle((x0, 342, x0 + 200, 600), 14, fill=(15, 23, 42), outline=(100, 116, 139), width=2)
    d.rectangle((x0 + 8, 352, x0 + 192, 376), fill=(6, 95, 70))
    d.text((x0 + 14, 354), "LINE 監控通報", font=F15, fill=(255, 255, 255))
    shown = [m for m in messages if m[0] <= t][-3:]
    yy = 384
    for mt, text in shown:
        lines = text.replace("🚨", "").splitlines()
        head = lines[0]
        where = next((l for l in lines if l.startswith("事件")), "")
        fresh = t - mt < 2
        d.rounded_rectangle((x0 + 10, yy, x0 + 190, yy + 62), 8, fill=(22, 101, 52) if fresh else (51, 65, 85))
        d.text((x0 + 16, yy + 4), head[:12], font=F13, fill=(255, 255, 255))
        d.text((x0 + 16, yy + 22), where[:13], font=F13, fill=(226, 232, 240))
        d.text((x0 + 16, yy + 40), f"演練 {mt:.1f} 秒", font=F13, fill=(203, 213, 225))
        yy += 70
    if not shown:
        d.text((x0 + 16, 390), "（尚無訊息）", font=F13, fill=(148, 163, 184))

    # 事件紀錄
    d.rounded_rectangle((x0 + 212, 342, W - 16, 600), 10, fill=(30, 41, 59), outline=(71, 85, 105))
    d.text((x0 + 224, 350), "事件紀錄", font=F17, fill=(255, 255, 255))
    recent = [e for e in log if e[0] <= t][-7:]
    for i, (et, text) in enumerate(recent):
        d.text((x0 + 224, 378 + i * 31), f"{et:5.1f}", font=FM14, fill=(148, 163, 184))
        d.text((x0 + 272, 376 + i * 31), text, font=F13, fill=(226, 232, 240))


def wrap(text, fnt, width):
    lines, cur = [], ""
    for ch in text:
        if fnt.getlength(cur + ch) > width:
            lines.append(cur)
            cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    # 避免標點出現在行首
    for i in range(1, len(lines)):
        if lines[i] and lines[i][0] in "，。、：；！？）」":
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    return lines


def draw_caption(canvas, title, text):
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 612, W, H), fill=(2, 6, 23))
    d.text((24, 620), title, font=F26B, fill=(253, 224, 71))
    for i, line in enumerate(wrap(text, F22, W - 48)[:2]):
        d.text((24, 656 + i * 30), line, font=F22, fill=(241, 245, 249))


def title_card(kind):
    img = Image.new("RGB", (W, H), (15, 23, 42))
    d = ImageDraw.Draw(img)
    if kind == "title":
        d.text((80, 200), "AI 守望：公共場所 AI 監控通報", font=F34B, fill=(255, 255, 255))
        d.text((80, 260), "動作要求示意影片（模擬動畫）", font=F26B, fill=(253, 224, 71))
        d.text((80, 330), "人物與偵測結果是事先安排的模擬；判斷規則、通報流程、警示盒畫面都和程式包相同。",
               font=F22, fill=(226, 232, 240))
        d.text((80, 370), "演練一律用剪刀或道具代替刀械，不在公共場所實際測試。", font=F22, fill=(252, 165, 165))
    else:
        d.text((80, 150), "重點整理", font=F34B, fill=(255, 255, 255))
        items = ["危險物品的框和人的框重疊才算「手持」，並且要持續 0.6 秒",
                 "高風險（持械、奔逃）先倒數 5 秒，保全可以按取消鈕標記誤報",
                 "中風險（倒地）直接發 LINE；低風險（聚集）只記錄",
                 "門檻調鬆會多抓到事件，但誤報也變多：用評估工具的數據決定",
                 "警示盒斷線要看得出來；系統只能輔助，不能取代保全與 110"]
        for i, s in enumerate(items):
            d.text((100, 230 + i * 56), f"{i + 1}. {s}", font=F26B if False else F22, fill=(226, 232, 240))
    return img


# ---------- 聲音 ----------
def build_audio(beeps, chimes, total):
    n = int(total * SR)
    audio = np.zeros(n, np.float32)
    beeps = np.array(beeps, bool)
    per = SR // FPS
    tone = 0.25 * np.sign(np.sin(2 * np.pi * 2300 * np.arange(n) / SR)).astype(np.float32)
    mask = np.repeat(beeps, per)[:n]
    audio[:len(mask)] += tone[:len(mask)] * mask
    for ct in chimes:
        for k, f in enumerate((1318, 1760)):
            i = int((ct + k * 0.12) * SR)
            seg = np.arange(int(0.18 * SR))
            s = 0.3 * np.sin(2 * np.pi * f * seg / SR) * np.exp(-seg / (0.08 * SR))
            end = min(n, i + len(seg))
            if i < n:
                audio[i:end] += s[:end - i].astype(np.float32)
    return (np.clip(audio, -1, 1) * 32767).astype(np.int16)


def main():
    global LABELS
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ff = shutil.which("ffmpeg")
    if not ff:
        raise SystemExit("找不到 ffmpeg，請先安裝（例如 winget install Gyan.FFmpeg）")
    LABELS = load_labels()
    detlog.OUTPUT.mkdir(parents=True, exist_ok=True)

    # TFT 預覽圖（手冊用）
    states = [(0, "N", 0, "監控中"), (1, "F", 0, "注意（倒地）"), (2, "W", 4, "警報倒數"),
              (3, "W", 0, "已通報"), (4, "C", 0, "已取消"), (-1, "N", 0, "未連線")]
    prev = Image.new("RGB", (6 * 336 + 16, 300), (255, 255, 255))
    pd = ImageDraw.Draw(prev)
    for i, (s, k, sec, name) in enumerate(states):
        prev.paste(tft_screen(s, k, sec).resize((320, 256), Image.NEAREST), (16 + i * 336, 12))
        pd.text((16 + i * 336 + 160 - F22.getlength(name) / 2, 272), name, font=F22, fill=(15, 23, 42))
    prev.save(detlog.OUTPUT / "tft_preview.png")

    print("模擬規則與通報流程…")
    rows, messages, log = simulate()
    total = sum(s[1] if isinstance(s[0], str) else s[1] - s[0] for s in SEGMENTS)
    tmp_video = str(detlog.OUTPUT / "_scenario_video.mp4")
    proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "24", "-pix_fmt", "yuv420p", tmp_video], stdin=subprocess.PIPE)
    cards = {k: title_card(k) for k in ("title", "end")}
    beeps, chimes, timeline = [], [], []
    vt = 0.0
    for seg in SEGMENTS:
        if isinstance(seg[0], str):
            for _ in range(int(seg[1] * FPS)):
                proc.stdin.write(cards[seg[0]].tobytes())
                beeps.append(False)
            vt += seg[1]
            continue
        t0, t1, title, text = seg
        timeline.append((vt, title))
        seg_msgs = [m for m in messages if t0 <= m[0] < t1]
        chimes += [vt + (m[0] - t0) for m in seg_msgs]
        last_state, last_sent = (0, None, 0), -1.0
        for f in range(int((t1 - t0) * FPS)):
            t = t0 + f / FPS
            row = rows[min(len(rows) - 1, int(round(t * ds.FPS)))]
            plugged = not (seg[0] == 173.0 and t >= UNPLUG_AT)
            if plugged and t - last_sent >= 0.2 - 1e-6:       # 電腦每 0.2 秒送一次狀態
                last_sent, last_state = t, row["state"]
            state = last_state if (plugged or t - last_sent <= 1.5) else (-1, None, 0)
            click = CANCEL_AT <= t < CANCEL_AT + 0.4
            frame = Image.new("RGB", (W, H), (15, 23, 42))
            dd = ImageDraw.Draw(frame)
            dd.text((16, 12), "AI 守望・動作要求示意（模擬動畫）", font=F26B, fill=(255, 255, 255))
            frame.paste(draw_camera(t, row), (CAM_X, CAM_Y))
            draw_legend(dd)
            draw_panel(frame, t, state, plugged, click, [m for m in messages if t0 <= m[0]],
                       [e for e in log if t0 <= e[0]])
            draw_caption(frame, title, text)
            beeps.append(box_outputs(state[0], t, click)[3])
            proc.stdin.write(frame.tobytes())
        vt += t1 - t0
        print(f"  {title}")
    proc.stdin.close()
    proc.wait()

    wav_path = detlog.OUTPUT / "_scenario_audio.wav"
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(build_audio(beeps, chimes, total).tobytes())
    out = detlog.OUTPUT / "scenario_demo.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", tmp_video, "-i", str(wav_path), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-shortest", str(out)], check=True)
    Path(tmp_video).unlink()
    wav_path.unlink()
    print(f"\n完成：{out}（{total:.0f} 秒）")
    print("\n影片時間表：")
    for vt, title in timeline:
        print(f"  {int(vt) // 60}:{int(vt) % 60:02d}  {title}")
    print("\n事件：")
    for t, e in log:
        print(f"  演練 {t:6.1f} 秒  {e}")


if __name__ == "__main__":
    main()
