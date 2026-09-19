"""頭部障礙物警示帽：筆電端主程式（筆電放在背包裡執行）。

分工：
  - ESP32（帽子上）：讀取左前、右前兩顆 ToF 測距，直接控制震動馬達，並把距離傳給筆電
  - 筆電（背包裡）：用 YOLO 辨識前方物體，透過骨傳導耳機用語音補充說明

語音提醒的三種情況：
  1. 很近：ToF 距離小於 near_mm → 「右前方有人，很近」或「前方有障礙，很近」
  2. 靠近：人、車等物體在畫面中快速變大 → 「注意，左前方有機車靠近」
  3. 按鈕：按下帽子上的按鈕 → 描述左、前、右各有什麼，以及最近距離

用法：
  python headgear_assist.py                          實際使用（背包模式，不開視窗）
  python headgear_assist.py --window                 開視窗除錯（按 b 描述前方、q 離開）
  python headgear_assist.py --no-serial --window     沒有接 ESP32 時測試鏡頭與辨識
  python headgear_assist.py --video demo.mp4 --fake-sensor demo_sensor.csv --window
"""
import argparse
import csv
import datetime as dt
import json
import os
import queue
import threading
import time
from collections import deque

import cv2
from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))

ZH = {
    "person": "人", "bicycle": "腳踏車", "car": "汽車", "motorcycle": "機車", "bus": "公車",
    "truck": "貨車", "traffic light": "紅綠燈", "fire hydrant": "消防栓", "stop sign": "停止標誌",
    "bench": "長椅", "dog": "狗", "cat": "貓", "backpack": "背包", "umbrella": "雨傘",
    "handbag": "手提包", "suitcase": "行李箱", "bottle": "瓶子", "cup": "杯子", "chair": "椅子",
    "couch": "沙發", "potted plant": "盆栽", "bed": "床", "dining table": "桌子", "toilet": "馬桶",
    "tv": "螢幕", "laptop": "筆電", "cell phone": "手機", "refrigerator": "冰箱", "book": "書",
    "clock": "時鐘", "vase": "花瓶", "sink": "洗手台", "microwave": "微波爐", "oven": "烤箱",
}
COUNT = {1: "一個", 2: "兩個", 3: "三個"}


def zh(name):
    return ZH.get(name, name)


def side_of(cx, width):
    if cx < width / 3:
        return "左前方"
    if cx > width * 2 / 3:
        return "右前方"
    return "前方"


def meters(mm):
    return f"約 {mm / 1000:.1f} 公尺"


# ---------- 語音 ----------
class Speaker:
    """背景語音：新的重要訊息會蓋掉還沒念的舊訊息，避免越講越慢。"""

    def __init__(self, enabled, rate):
        self.enabled = enabled
        self.q = queue.Queue()
        if enabled:
            threading.Thread(target=self._run, args=(rate,), daemon=True).start()

    def _run(self, rate):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            for v in engine.getProperty("voices"):
                tag = f"{v.id} {v.name}".lower()
                if any(k in tag for k in ("zh-tw", "zh_tw", "chinese", "hanhan", "yating", "zhiwei", "huihui")):
                    engine.setProperty("voice", v.id)
                    break
        except Exception as e:
            print("語音初始化失敗（只會印出文字）：", e)
            engine = None
        while True:
            text = self.q.get()
            if engine is None:
                continue
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print("語音播放失敗：", e)

    def say(self, text, urgent=False):
        print("[語音]", text)
        if not self.enabled:
            return
        if urgent:
            while not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
        self.q.put(text)


# ---------- 感測器 ----------
class SensorLink:
    """讀取 ESP32 傳來的距離與按鈕事件。"""

    def __init__(self, port, baud):
        self.left = self.right = -1
        self.updated = 0.0
        self.buttons = queue.Queue()
        self.ser = None
        port = self._find_port() if port == "auto" else port
        if not port:
            print("找不到 ESP32 的序列埠，請確認 USB 線，或在 config.json 指定 serial_port")
            return
        import serial
        self.ser = serial.Serial(port, baud, timeout=1)
        print("已連線 ESP32：", port)
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def _find_port():
        try:
            from serial.tools import list_ports
        except ImportError:
            print("尚未安裝 pyserial：pip install pyserial")
            return None
        keys = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "usb jtag", "uart")
        for p in list_ports.comports():
            desc = f"{p.description} {p.manufacturer or ''}".lower()
            if any(k in desc for k in keys):
                return p.device
        return None

    def _run(self):
        while True:
            try:
                line = self.ser.readline().decode("ascii", "ignore").strip()
            except Exception as e:
                print("序列埠讀取失敗：", e)
                time.sleep(1)
                continue
            if line.startswith("D,"):
                parts = line.split(",")
                if len(parts) == 3:
                    try:
                        self.left, self.right = int(parts[1]), int(parts[2])
                        self.updated = time.time()
                    except ValueError:
                        pass
            elif line == "B":
                self.buttons.put(time.time())
            elif line.startswith("I,"):
                print("ESP32 狀態：", line)

    def test_motors(self):
        if self.ser:
            self.ser.write(b"T")

    def connected(self, now):
        return self.ser is not None and now - self.updated < 2.0


class FakeSensor:
    """從 CSV 讀取模擬的距離與按鈕（time,left,right,button），配合測試影片使用。"""

    def __init__(self, path):
        self.rows = []
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                self.rows.append((float(r["time"]), int(r["left"]), int(r["right"]), r.get("button", "") == "1"))
        self.idx = 0
        self.left = self.right = -1
        self.buttons = queue.Queue()
        self.updated = 0.0

    def update(self, t):
        while self.idx < len(self.rows) and self.rows[self.idx][0] <= t:
            _, self.left, self.right, pressed = self.rows[self.idx]
            if pressed:
                self.buttons.put(t)
            self.idx += 1
        self.updated = t

    def test_motors(self):
        pass

    def connected(self, now):
        return True


class NoSensor:
    left = right = -1
    updated = 0.0

    def __init__(self):
        self.buttons = queue.Queue()

    def test_motors(self):
        pass

    def connected(self, now):
        return True


# ---------- 主程式 ----------
def describe(dets, left, right):
    parts = []
    for side in ("左前方", "前方", "右前方"):
        names = [d["name"] for d in dets if d["side"] == side]
        if not names:
            continue
        counts = {}
        for n in names:
            counts[n] = counts.get(n, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        words = "、".join(f"{COUNT.get(c, f'{c} 個')}{zh(n)}" for n, c in top)
        parts.append(f"{side}有{words}")
    text = "；".join(parts) if parts else "前方沒有辨識到物體"
    valid = [v for v in (left, right) if v > 0]
    if valid:
        text += f"。最近的障礙{meters(min(valid))}"
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--window", action="store_true", help="顯示除錯視窗")
    parser.add_argument("--no-serial", action="store_true", help="不連接 ESP32")
    parser.add_argument("--video", help="用影片檔取代攝影機")
    parser.add_argument("--fake-sensor", help="模擬感測器資料 CSV")
    parser.add_argument("--no-voice", action="store_true")
    args = parser.parse_args()

    cfg_path = args.config if os.path.isabs(args.config) or os.path.exists(args.config) else os.path.join(HERE, args.config)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    show = args.window or cfg.get("show_window", False)
    speaker = Speaker(cfg.get("voice", True) and not args.no_voice, cfg.get("speech_rate", 200))

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(HERE, p)

    if args.fake_sensor:
        sensor = FakeSensor(resolve(args.fake_sensor))
    elif args.no_serial:
        sensor = NoSensor()
    else:
        sensor = SensorLink(cfg.get("serial_port", "auto"), cfg.get("baud", 115200))

    if args.video:
        cap = cv2.VideoCapture(resolve(args.video))
        is_video = True
    else:
        cap = cv2.VideoCapture(cfg["camera"], cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(cfg["camera"])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["camera_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["camera_height"])
        is_video = False
    if not cap.isOpened():
        speaker.say("找不到鏡頭，請檢查 USB 線", urgent=True)
        time.sleep(3)
        raise SystemExit("無法開啟鏡頭")

    log_dir = resolve(cfg.get("log_dir", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, dt.datetime.now().strftime("session_%Y%m%d_%H%M%S.csv"))
    log_f = open(log_path, "w", newline="", encoding="utf-8-sig")
    log = csv.writer(log_f)
    log.writerow(["time", "event", "left_mm", "right_mm", "text"])

    model = YOLO(cfg["model"])
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    approach_ids = set(cfg["approach_classes"])
    near_mm = cfg["near_mm"]
    cooldown = cfg["repeat_cooldown_sec"]

    dets = []
    history = {}          # (類別, 方位) → deque[(時間, 面積比例)]
    last_said = {}        # 訊息類型 → 上次時間
    last_detect = -1e9
    frame_idx = 0
    sensor_lost_said = False
    start = time.time()

    speaker.say("系統啟動完成")
    sensor.test_motors()

    def event(t, kind, text, urgent=False):
        speaker.say(text, urgent=urgent)
        log.writerow([round(t, 2), kind, sensor.left, sensor.right, text])
        log_f.flush()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if is_video:
                    break
                time.sleep(0.05)
                continue
            now = frame_idx / fps if is_video else time.time() - start
            frame_idx += 1
            if isinstance(sensor, FakeSensor):
                sensor.update(now)
            h, w = frame.shape[:2]

            # 物件辨識
            if now - last_detect >= cfg["detect_interval_sec"]:
                last_detect = now
                res = model(frame, conf=cfg["confidence"], imgsz=cfg.get("imgsz", 480), verbose=False)[0]
                dets = []
                for b in res.boxes:
                    x1, y1, x2, y2 = [int(v) for v in b.xyxy[0].tolist()]
                    name = model.names[int(b.cls[0])]
                    area = (x2 - x1) * (y2 - y1) / float(w * h)
                    dets.append({"name": name, "box": (x1, y1, x2, y2), "side": side_of((x1 + x2) / 2, w),
                                 "area": area})
                # 靠近判斷：同類別、同方位的最大物體，面積在短時間內明顯變大
                seen = set()
                for d in sorted(dets, key=lambda d: -d["area"]):
                    key = (d["name"], d["side"])
                    if d["name"] not in approach_ids or key in seen:
                        continue
                    seen.add(key)
                    hist = history.setdefault(key, deque())
                    hist.append((now, d["area"]))
                    while hist and now - hist[0][0] > cfg["approach_window_sec"]:
                        hist.popleft()
                    old = hist[0][1]
                    if (len(hist) >= 3 and d["area"] > 0.04 and old > 0 and d["area"] / old >= cfg["approach_ratio"]
                            and now - last_said.get(("approach", key), -1e9) > cooldown):
                        last_said[("approach", key)] = now
                        event(now, "approach", f"注意，{d['side']}有{zh(d['name'])}靠近", urgent=True)
                for key in list(history):
                    if key not in seen:
                        del history[key]

            # 很近：以 ToF 距離為準，再用辨識結果補充是什麼
            left, right = sensor.left, sensor.right
            near_l = 0 < left < near_mm
            near_r = 0 < right < near_mm
            if (near_l or near_r) and now - last_said.get("near", -1e9) > cooldown:
                side = "前方" if near_l and near_r else ("左前方" if near_l else "右前方")
                cands = [d for d in dets if d["side"] == side or side == "前方"]
                what = zh(max(cands, key=lambda d: d["area"])["name"]) if cands else "障礙"
                dist = min(v for v in (left, right) if v > 0)
                last_said["near"] = now
                event(now, "near", f"{side}有{what}，很近，{meters(dist)}", urgent=True)

            # 按鈕：描述前方
            try:
                sensor.buttons.get_nowait()
                event(now, "button", describe(dets, left, right))
            except queue.Empty:
                pass

            # 感測器斷線提醒
            if not sensor.connected(time.time()):
                if not sensor_lost_said and time.time() - start > 5:
                    sensor_lost_said = True
                    event(now, "sensor_lost", "距離感測器沒有回應，請檢查帽子的 USB 線", urgent=True)
            else:
                sensor_lost_said = False

            if show:
                view = frame.copy()
                for d in dets:
                    x1, y1, x2, y2 = d["box"]
                    cv2.rectangle(view, (x1, y1), (x2, y2), (0, 200, 255), 2)
                    cv2.putText(view, d["name"], (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
                cv2.line(view, (w // 3, 0), (w // 3, h), (120, 120, 120), 1)
                cv2.line(view, (w * 2 // 3, 0), (w * 2 // 3, h), (120, 120, 120), 1)
                cv2.rectangle(view, (0, 0), (w, 30), (0, 0, 0), -1)
                cv2.putText(view, f"L {left} mm   R {right} mm   b=describe q=quit", (8, 21),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow("Headgear Assist", view)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("b"):
                    sensor.buttons.put(now)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        log_f.close()
        print("紀錄已存到：", log_path)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
