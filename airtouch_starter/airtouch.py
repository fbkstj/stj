"""AirTouch 無接觸手勢＋語音遙控：主程式。

用法：
  python airtouch.py                      正式使用（鏡頭＋麥克風，會真的操作 YouTube）
  python airtouch.py --dry-run            模擬模式：只顯示會做什麼，不會按鍵
  python airtouch.py --text               用打字代替說話（沒有麥克風時）
  python airtouch.py --no-voice           只用手勢
  python airtouch.py --profile powerpoint     固定使用簡報模式（不自動切換）
  python airtouch.py --video 手勢.mp4 --dry-run --headless   用錄好的影片測試

應用程式模式：預設會看「最前面的視窗」自動切換（YouTube、PowerPoint、PDF、Teams、Zoom、Meet），
同一個手勢在不同模式做不同的事，例如食指向右：YouTube＝快轉、簡報＝下一頁。

視窗按鍵：
  q／Esc 結束   g 手勢鎖   v 語音開關   p 換模式（固定）   a 自動切換模式   n 簡報備忘稿
  t 視窗置頂    o 透明度   s 小視窗     h 說明             d 除錯資訊
"""
import argparse
import csv
import datetime as dt
import json
import os
import queue
import time
import urllib.request
from collections import Counter

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import gestures
import ppt_com
from actions import ACTION_TEXT, Actions, match_profile, window_title
from voice_listener import VoiceListener

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = "AirTouch"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
HAND_LINES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
              (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def set_dpi_aware():
    """讓座標和螢幕像素一致（高解析度螢幕縮放 125%、150% 時，點擊位置才會準）。"""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def load_model(path):
    if not os.path.exists(path):
        print("第一次執行，下載手部模型（約 8 MB）…")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, path)
    with open(path, "rb") as f:               # 用位元組載入，資料夾有中文也沒問題
        return f.read()


def make_detector(model_bytes, cfg):
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    opt = vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_buffer=model_bytes),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=cfg["min_detection_confidence"],
        min_tracking_confidence=cfg["min_tracking_confidence"],
    )
    return vision.HandLandmarker.create_from_options(opt)


# ---------- 畫面 ----------
class Painter:
    """OpenCV 不能寫中文，改用 Pillow 寫字。"""

    def __init__(self):
        self.fonts = {}
        for path in ("C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/mingliu.ttc", "C:/Windows/Fonts/simsun.ttc"):
            if os.path.exists(path):
                self.path = path
                break
        else:
            self.path = None

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = ImageFont.truetype(self.path, size) if self.path else ImageFont.load_default()
        return self.fonts[size]

    def texts(self, img, items):
        """items: [(文字, (x, y), 字級, (R, G, B)), ...]，一次畫完比較快。"""
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        for text, pos, size, color in items:
            draw.text(pos, text, font=self.font(size), fill=color)
        img[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def draw_hand(view, pts, progress, locked):
    for a, b in HAND_LINES:
        cv2.line(view, tuple(pts[a].astype(int)), tuple(pts[b].astype(int)), (255, 200, 0), 2, cv2.LINE_AA)
    for i, p in enumerate(pts):
        cv2.circle(view, tuple(p.astype(int)), 6 if i in (4, 8, 12, 16, 20) else 3, (0, 255, 200), -1, cv2.LINE_AA)
    center = tuple(((pts[0] + pts[9]) / 2).astype(int))
    color = (120, 120, 255) if locked else (0, int(160 + 95 * progress), int(255 * progress))
    cv2.circle(view, center, 34, (70, 70, 70), 4, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(view, center, (34, 34), 0, -90, -90 + int(360 * progress), color, 5, cv2.LINE_AA)


class FloatingWindow:
    """視窗置頂與半透明（只有 Windows）。"""

    def __init__(self):
        self.topmost = False
        self.alpha_steps = [255, 191, 128]
        self.alpha_idx = 0

    def _hwnd(self):
        try:
            import win32gui
            return win32gui.FindWindow(None, WINDOW)
        except ImportError:
            return 0

    def set_topmost(self, on):
        hwnd = self._hwnd()
        if not hwnd:
            return
        import win32con
        import win32gui
        self.topmost = on
        flag = win32con.HWND_TOPMOST if on else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(hwnd, flag, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    def cycle_alpha(self):
        hwnd = self._hwnd()
        if not hwnd:
            return 100
        import win32con
        import win32gui
        self.alpha_idx = (self.alpha_idx + 1) % len(self.alpha_steps)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
        win32gui.SetLayeredWindowAttributes(hwnd, 0, self.alpha_steps[self.alpha_idx], win32con.LWA_ALPHA)
        return round(self.alpha_steps[self.alpha_idx] / 255 * 100)


class ProfileManager:
    """決定目前是哪個應用程式模式：自動看最前面的視窗，或手動固定。"""

    def __init__(self, cfg, fixed=None):
        self.cfg = cfg
        self.names = list(cfg["profiles"])
        self.current = fixed or cfg["default_profile"]
        self.auto = cfg.get("auto_switch_profile", True) and not fixed
        self.last_check = 0.0

    def gestures(self):
        return self.cfg["profiles"][self.current]["gestures"]

    def poll(self):
        """自動模式下，每隔一段時間檢查前景視窗；模式有變化時回傳新名稱。"""
        if not self.auto or os.name != "nt" or time.time() - self.last_check < self.cfg["profile_check_sec"]:
            return None
        self.last_check = time.time()
        import win32gui
        name = match_profile(self.cfg["profiles"], window_title(win32gui.GetForegroundWindow()))
        if name and name != self.current:
            self.current = name
            return name
        return None

    def set(self, name):
        self.current, self.auto = name, False

    def cycle(self):
        self.set(self.names[(self.names.index(self.current) + 1) % len(self.names)])

    def label(self):
        return f"{self.cfg['profiles'][self.current]['name']}（{'自動' if self.auto else '固定'}）"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--dry-run", action="store_true", help="模擬模式，不會真的按鍵")
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--text", action="store_true", help="用打字代替語音")
    parser.add_argument("--video", help="用影片檔代替鏡頭")
    parser.add_argument("--headless", action="store_true", help="不開視窗（測試用）")
    parser.add_argument("--profile", help="固定使用某個模式，例如 powerpoint")
    args = parser.parse_args()

    with open(resolve(args.config), encoding="utf-8") as f:
        cfg = json.load(f)
    set_dpi_aware()
    if args.profile and args.profile not in cfg["profiles"]:
        raise SystemExit(f"沒有「{args.profile}」模式，可用的有：{', '.join(cfg['profiles'])}")
    actions = Actions(cfg, dry_run=args.dry_run)
    profiles = ProfileManager(cfg, args.profile)
    trigger = gestures.GestureTrigger(cfg, profiles.gestures())
    detector = make_detector(load_model(resolve(cfg["model_path"])), cfg)
    import mediapipe as mp
    painter = Painter()
    floating = FloatingWindow()

    if args.video:
        cap = cv2.VideoCapture(resolve(args.video))
    else:
        cam = cfg["camera"]
        cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(cam)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["camera_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["camera_height"])
    if not cap.isOpened():
        raise SystemExit("無法開啟鏡頭或影片，請檢查 config.json 的 camera")
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(resolve("logs"), exist_ok=True)
    log_path = resolve(os.path.join("logs", f"session_{stamp}.csv"))
    log_f = open(log_path, "w", newline="", encoding="utf-8-sig")
    log = csv.writer(log_f)
    log.writerow(["time", "profile", "source", "input", "action", "arg", "ok", "message", "hold_or_recog_sec"])
    start = time.time()

    toast = {"text": "AirTouch 啟動完成" + ("（模擬模式）" if args.dry_run else ""), "until": time.time() + 3, "ok": True}
    voice_state = {"text": "語音關閉" if args.no_voice else "語音啟動中"}
    commands = queue.Queue()

    def on_voice(text, cmd, cost):
        commands.put((text, cmd, cost))

    def on_status(text):
        voice_state["text"] = text

    listener = None
    if not args.no_voice:
        listener = VoiceListener(cfg, on_voice, on_status, text_mode=args.text)
        listener.start()

    stats = Counter()
    frames = 0
    last_ts = -1
    show_help = show_debug = small = show_notes = False
    ppt_state, ppt_checked = None, 0.0
    running = True
    fps = 0.0
    fps_t, fps_n = time.time(), 0

    def write_log(source, raw, action, arg, ok, msg, extra):
        now = time.time() - start
        stats[(source, action, ok)] += 1
        log.writerow([round(now, 2), profiles.current, source, raw, action,
                      json.dumps(arg, ensure_ascii=False) if arg else "", int(ok), msg, extra])
        log_f.flush()
        print(f"[{now:7.2f}s] {profiles.current}｜{source}：{raw} → {msg}")

    def change_profile(name, source, raw=None, extra=""):
        trigger.set_map(profiles.gestures())
        msg = f"切換到「{cfg['profiles'][name]['name']}」模式"
        toast.update(text=msg, until=time.time() + 2.5, ok=True)
        write_log(source, raw or name, "switch_profile", name, True, msg, extra)

    def execute(source, raw, action, arg, extra):
        nonlocal running
        ok, msg, real = actions.run(action, arg, profiles.current)
        if ok and real == "exit":
            running = False
        elif ok and real in ("lock", "unlock"):
            trigger.locked = real == "lock"
        elif ok and real == "switch_profile":
            name = actions.meeting_profile() if arg == "meeting" else arg
            if name not in cfg["profiles"]:
                ok, msg = False, f"沒有「{arg}」模式"
            else:
                profiles.set(name)
                change_profile(name, source, raw, extra)
                return
        elif ok and real == "auto_profile":
            profiles.auto = True
            profiles.last_check = 0.0
            msg = "已開啟自動切換模式"
        toast.update(text=("完成：" if ok else "失敗：") + msg, until=time.time() + 2.5, ok=ok)
        write_log(source, raw, real, arg, ok, msg, extra)

    if not args.headless:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, cfg["camera_width"], cfg["camera_height"])
        if cfg.get("window_topmost", True):
            cv2.waitKey(1)
            floating.set_topmost(True)
    print("AirTouch 開始運作；在視窗按 h 看說明、q 結束")

    try:
        while running:
            ok, frame = cap.read()
            if not ok:
                if args.video:
                    break
                time.sleep(0.05)
                continue
            if cfg.get("mirror", True) and not args.video:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            frames += 1
            ts = int(frames / video_fps * 1000) if args.video else int((time.time() - start) * 1000)
            ts = max(ts, last_ts + 1)
            last_ts = ts
            now = ts / 1000

            result = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), ts)

            # 畫面上有多隻手時，取最大（最靠近鏡頭）的那一隻
            pts, gesture, info = None, "no_hand", {}
            if result.hand_landmarks:
                hands = [gestures.to_pixels([(p.x, p.y) for p in lm], w, h) for lm in result.hand_landmarks]
                pts = max(hands, key=lambda q: np.hypot(*(q[0] - q[9])))
                gesture, info = gestures.analyze(pts, h, cfg)

            changed = profiles.poll()
            if changed:
                change_profile(changed, "auto")

            stable, progress, event = trigger.update(gesture, now)
            if event:
                execute("gesture", gestures.GESTURE_NAMES.get(event["gesture"], event["gesture"]),
                        event["action"], profiles.gestures().get(event["gesture"], {}).get("arg"), event["held"])

            while not commands.empty():
                text, cmd, cost = commands.get()
                if cmd is None:
                    toast.update(text=f"聽不懂：「{text}」", until=time.time() + 2.5, ok=False)
                    write_log("voice", text, "unknown", None, False, "聽不懂", round(cost, 2))
                else:
                    execute("voice", text, cmd["action"], cmd["arg"], round(cost, 2))

            fps_n += 1
            if time.time() - fps_t >= 1.0:
                fps, fps_t, fps_n = fps_n / (time.time() - fps_t), time.time(), 0

            if args.headless:
                continue

            # 簡報模式：每秒讀一次頁碼與備忘稿
            if profiles.current == "powerpoint" and time.time() - ppt_checked > 1.0:
                ppt_checked = time.time()
                ppt_state = ppt_com.state()
            elif profiles.current != "powerpoint":
                ppt_state = None

            view = frame
            if pts is not None:
                draw_hand(view, pts, progress, trigger.locked)
            bar_color = (60, 60, 160) if trigger.locked else (40, 40, 40)
            cv2.rectangle(view, (0, 0), (w, 64), bar_color, -1)
            page = ""
            if ppt_state:
                page = f"   第 {ppt_state['index']}／{ppt_state['total']} 頁" + ("" if ppt_state["show"] else "（編輯中）")
            items = [
                (f"模式：{profiles.label()}  |  {'［手勢鎖定：握拳解鎖］' if trigger.locked else '手勢啟用'}"
                 f"  |  {voice_state['text']}", (10, 7), 16, (255, 255, 255)),
                (f"手勢：{gestures.GESTURE_NAMES.get(stable, stable)}"
                 + (f"（{int(progress * 100)}%）" if 0 < progress < 1 else "")
                 + page + f"   {fps:4.1f} FPS" + ("   模擬模式" if args.dry_run else ""),
                 (10, 34), 18, (255, 230, 120)),
            ]
            if show_notes and ppt_state:
                note = ppt_state["notes"] or "（這頁沒有備忘稿）"
                lines = [note[i:i + 30] for i in range(0, min(len(note), 90), 30)]
                top = h - 50 - 26 * len(lines) - 30
                cv2.rectangle(view, (0, top), (w, h - 46), (60, 40, 20), -1)
                items.append((f"備忘稿｜{ppt_state['title'][:24]}", (12, top + 4), 16, (255, 220, 150)))
                for i, line in enumerate(lines):
                    items.append((line, (12, top + 30 + 26 * i), 20, (255, 255, 255)))
            if time.time() < toast["until"]:
                cv2.rectangle(view, (0, h - 44), (w, h), (30, 90, 30) if toast["ok"] else (30, 30, 90), -1)
                items.append((toast["text"], (12, h - 36), 20, (255, 255, 255)))
            if show_debug and info.get("extended"):
                e = info["extended"]
                flags = " ".join(f"{k}:{'伸' if v else '彎'}" for k, v in e.items())
                items.append((f"{flags}  手掌 {info['palm']:.0f}px", (10, 70), 16, (200, 255, 200)))
            if show_help:
                lines = [(f"目前模式：{cfg['profiles'][profiles.current]['name']}", (255, 230, 120))]
                for g, spec in profiles.gestures().items():
                    lines.append((f"{gestures.GESTURE_NAMES[g]}（{spec['hold_sec']} 秒）→ {ACTION_TEXT[spec['action']]}",
                                  (255, 255, 255)))
                lines.append((f"握拳 {cfg['lock_hold_sec']} 秒 → 手勢鎖定／解鎖", (255, 200, 200)))
                lines.append(("q 結束  g 鎖定  v 語音  p 換模式  a 自動  n 備忘稿", (180, 220, 255)))
                lines.append(("t 置頂  o 透明  s 小視窗  d 除錯", (180, 220, 255)))
                step = min(24, (h - 150) // len(lines))            # 畫面比較矮時，行距自動縮小
                size = max(12, min(16, step - 6))
                cv2.rectangle(view, (20, 70), (w - 20, 78 + step * len(lines)), (20, 20, 20), -1)
                for k, (text, color) in enumerate(lines):
                    items.append((text, (32, 74 + step * k), size, color))
            painter.texts(view, items)
            if small:
                view = cv2.resize(view, (w // 2, h // 2))
            cv2.imshow(WINDOW, view)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("g"):
                execute("key", "g", "unlock" if trigger.locked else "lock", None, "")
            elif key == ord("v") and listener:
                listener.enabled = not listener.enabled
                voice_state["text"] = "語音待命中" if listener.enabled else "語音暫停（按 v 開啟）"
            elif key == ord("p"):
                profiles.cycle()
                change_profile(profiles.current, "key")
            elif key == ord("a"):
                execute("key", "a", "auto_profile", None, "")
            elif key == ord("n"):
                show_notes = not show_notes
                if show_notes and not ppt_state:
                    toast.update(text="備忘稿只在簡報模式、PowerPoint 開著時顯示", until=time.time() + 2.5, ok=False)
            elif key == ord("t"):
                floating.set_topmost(not floating.topmost)
                toast.update(text=f"視窗置頂：{'開' if floating.topmost else '關'}", until=time.time() + 2, ok=True)
            elif key == ord("o"):
                toast.update(text=f"視窗不透明度：{floating.cycle_alpha()}%", until=time.time() + 2, ok=True)
            elif key == ord("s"):
                small = not small
                cv2.resizeWindow(WINDOW, w // 2 if small else w, h // 2 if small else h)
            elif key == ord("h"):
                show_help = not show_help
            elif key == ord("d"):
                show_debug = not show_debug
            if not args.video and cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if listener:
            listener.stop()
        cap.release()
        cv2.destroyAllWindows()
        detector.close()
        log_f.close()
        duration = time.time() - start
        summary = {
            "duration_sec": round(duration, 1),
            "frames": frames,
            "avg_fps": round(frames / max(duration, 1e-6), 1),
            "dry_run": args.dry_run,
            "events": [{"source": s, "action": a, "ok": ok, "count": n} for (s, a, ok), n in sorted(stats.items())],
        }
        with open(os.path.splitext(log_path)[0] + ".json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"結束：{summary['duration_sec']} 秒、平均 {summary['avg_fps']} FPS、動作 {sum(stats.values())} 次")
        print("紀錄已存到：", log_path)


if __name__ == "__main__":
    main()
