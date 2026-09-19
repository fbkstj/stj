"""自行車「後方來車」警示：主程式。

做法：
  1. 用 YOLO 找出後方影像裡的汽車、機車、公車、貨車
  2. 追蹤同一台車，記錄它的框寬度隨時間的變化
  3. 框的寬度和距離成反比，由此估計還有幾秒會到（τ，碰撞前時間）
  4. τ 小於 ttc_warn 秒 → 注意（黃燈、短嗶）；小於 ttc_danger 秒 → 危險（紅燈、連續嗶）
  5. 說出車種（後方機車／汽車／大型車），ESP32 的 TFT 顯示等級、車種與到達秒數（見 voice.py）

輸出：
  logs/<影片名>_<時間>.csv          每次警示開始、升級、解除的時間
  logs/<影片名>_<時間>.json         這次分析的摘要（長度、車輛數、警示次數、處理速度）
  output/<影片名>_<時間>.mp4        標註影片（加 --save 才有，已模糊行人與車牌）
  output/snapshots/<影片名>_<時間>/  每次警示開始的截圖（已模糊）

用法：
  python rear_alert.py --video demo.mp4 --window              分析影片（開視窗看過程）
  python rear_alert.py --video 我的影片.mp4 --save              分析影片並輸出標註影片
  python rear_alert.py --camera --window                        桌上模型展示（用鏡頭，連接 ESP32）
  python rear_alert.py --camera --window --no-serial            沒有 ESP32 時，用電腦嗶聲代替

不要邊騎車邊看這個程式的畫面；請用錄好的影片或桌上模型測試。
"""
import argparse
import csv
import datetime as dt
import json
import os
import time
from collections import Counter, deque

import cv2
import numpy as np
from ultralytics import YOLO

import voice

HERE = os.path.dirname(os.path.abspath(__file__))
LEVEL_NAME = {0: "安全", 1: "注意", 2: "危險"}
LEVEL_COLOR = {0: (80, 180, 60), 1: (0, 200, 255), 2: (40, 40, 230)}   # BGR
LEVEL_TEXT = {0: "SAFE", 1: "CAUTION", 2: "DANGER"}


def resolve(p):
    return p if os.path.isabs(p) else os.path.join(HERE, p)


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


# ---------- 追蹤 ----------
class Track:
    def __init__(self, tid, det, t):
        self.id = tid
        self.name = det["name"]
        self.box = det["box"]
        self.last_seen = t
        self.sizes = deque()        # (時間, 框寬度的倒數)
        self.ttc = None
        self.hits = 0               # 連續幾次判定為逼近
        self.level = 0              # 這台車目前的警示等級（畫框顏色用）

    def add(self, det, t, window):
        self.box = det["box"]
        self.name = det["name"]
        self.last_seen = t
        x1, y1, x2, y2 = self.box
        # 用寬度不用高度：車很近時，車頂常超出畫面上緣，高度會被切掉
        self.sizes.append((t, 1.0 / max(1, x2 - x1)))
        while self.sizes and t - self.sizes[0][0] > window:
            self.sizes.popleft()

    def estimate_ttc(self, min_points):
        """估計還有幾秒到達（τ）。

        框的寬度和距離成反比，所以「寬度的倒數」和距離成正比。
        車子等速靠近時，寬度倒數會隨時間直線下降，
        用最小平方法畫一條直線，看它還要多久降到 0，就是到達時間。
        """
        if len(self.sizes) < min_points:
            return None
        ts = np.array([p[0] for p in self.sizes])
        inv = np.array([p[1] for p in self.sizes])
        if ts[-1] - ts[0] < 0.2:
            return None
        slope, intercept = np.polyfit(ts - ts[-1], inv, 1)
        if slope >= 0 or intercept <= 0:
            return None                              # 沒有變近（距離不變或變遠）
        return intercept / -slope


class Tracker:
    """簡單追蹤器：新的框和上一次的框重疊最多（IoU）就當成同一台車。"""

    def __init__(self, cfg):
        self.tracks = []
        self.next_id = 1
        self.cfg = cfg
        self.counts = Counter()     # 各車種出現過幾台（摘要用）

    def update(self, dets, t):
        unused = list(range(len(dets)))
        for tr in sorted(self.tracks, key=lambda k: -k.last_seen):
            best, best_iou = None, self.cfg["match_iou"]
            for i in unused:
                v = iou(tr.box, dets[i]["box"])
                if v > best_iou:
                    best, best_iou = i, v
            if best is not None:
                tr.add(dets[best], t, self.cfg["size_window_sec"])
                unused.remove(best)
        for i in unused:
            tr = Track(self.next_id, dets[i], t)
            tr.add(dets[i], t, self.cfg["size_window_sec"])
            self.tracks.append(tr)
            self.counts[tr.name] += 1
            self.next_id += 1
        self.tracks = [tr for tr in self.tracks if t - tr.last_seen <= self.cfg["lost_sec"]]
        return [tr for tr in self.tracks if tr.last_seen == t]


# ---------- 警示狀態 ----------
class AlertState:
    """警示等級的狀態機：升級立刻生效，降級要等 hold_sec 秒，避免燈號一直閃。"""

    def __init__(self, hold_sec):
        self.hold = hold_sec
        self.level = 0
        self.until = -1.0
        self.on = False

    def update(self, want, now):
        """回傳這次要記錄的事件：alert_on、escalate、alert_off 或 None。"""
        event = None
        if want > 0:
            if not self.on:
                event = "alert_on"
            elif want > self.level:
                event = "escalate"
            self.on = True
            if want >= self.level or now >= self.until:
                self.level = want
                self.until = now + self.hold
        elif self.on and now >= self.until:
            event = "alert_off"
            self.level, self.on = 0, False
        return event


# ---------- 警示輸出 ----------
class Esp32Link:
    """把狀態（S＋等級＋車種＋秒數）、語音編號（P1～P9）、音量（V0～V30）傳給 ESP32，
    由 ESP32 控制燈號、蜂鳴器、TFT 文字與 DFPlayer 語音。"""

    def __init__(self, port, baud):
        self.ser = None
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            print("尚未安裝 pyserial：pip install pyserial（先改用電腦嗶聲）")
            return
        if port == "auto":
            keys = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "usb jtag", "uart")
            port = next((p.device for p in list_ports.comports()
                         if any(k in f"{p.description} {p.manufacturer or ''}".lower() for k in keys)), None)
        if not port:
            print("找不到 ESP32 的序列埠（先改用電腦嗶聲），可在 config.json 指定 serial_port")
            return
        try:
            self.ser = serial.Serial(port, baud, timeout=0)
            time.sleep(2)            # ESP32 連線時會重新開機
            print("已連線 ESP32：", port)
        except Exception as e:
            print("無法開啟序列埠：", e)

    def send(self, text):
        if self.ser:
            try:
                self.ser.write(f"{text}\n".encode())
                return True
            except Exception as e:
                print("序列埠寫入失敗，ESP32 會顯示離線：", e)
                self.ser = None
        return False


class PcBeeper:
    """沒有 ESP32 時，用電腦發出嗶聲（只有 Windows）。"""

    def __init__(self, enabled):
        self.enabled = enabled and os.name == "nt"
        self.last = 0.0
        self.quiet_until = 0.0      # 播放語音時暫停嗶聲

    def update(self, level):
        if not self.enabled or level == 0 or time.time() < self.quiet_until:
            return
        import winsound
        now = time.time()
        if level == 2 and now - self.last > 0.3:
            winsound.Beep(1800, 120)
            self.last = now
        elif level == 1 and now - self.last > 1.0:
            winsound.Beep(1000, 80)
            self.last = now


# ---------- 畫面 ----------
def blur_privacy(view, tracks, persons):
    """把行人整個模糊、把車輛下半部（車牌位置）模糊。"""
    boxes = list(persons)
    for tr in tracks:
        x1, y1, x2, y2 = tr.box
        boxes.append((x1, int(y1 + (y2 - y1) * 0.55), x2, y2))
    for x1, y1, x2, y2 in boxes:
        x1, y1 = max(0, x1), max(0, y1)
        roi = view[y1:y2, x1:x2]
        if roi.size:
            view[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (0, 0), 12)


def draw_overlay(view, tracks, level, now, zone, note=""):
    h, w = view.shape[:2]
    zx1, zx2 = int(zone[0] * w), int(zone[1] * w)
    cv2.rectangle(view, (zx1, 0), (zx2 - 1, h - 1), (200, 200, 200), 1)
    for tr in tracks:
        x1, y1, x2, y2 = tr.box
        color = LEVEL_COLOR[tr.level]
        cv2.rectangle(view, (x1, y1), (x2, y2), color, 2)
        label = f"{tr.name}#{tr.id}" + (f" {tr.ttc:.1f}s" if tr.ttc is not None and tr.ttc < 99 else "")
        ty = y1 - 6 if y1 > 56 else max(y1, 34) + 22      # 太靠上就寫在框內，避免被狀態列蓋住
        cv2.putText(view, label, (max(0, x1) + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    cv2.rectangle(view, (0, 0), (w, 34), LEVEL_COLOR[level], -1)
    cv2.putText(view, f"{LEVEL_TEXT[level]}   t={now:5.1f}s  {note}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                (255, 255, 255), 2)


def main():
    parser = argparse.ArgumentParser()
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--video", help="要分析的影片檔")
    src.add_argument("--camera", action="store_true", help="使用鏡頭（桌上模型展示）")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--window", action="store_true", help="顯示畫面（q 離開、空白鍵暫停）")
    parser.add_argument("--save", action="store_true", help="輸出標註影片到 output/")
    parser.add_argument("--no-serial", action="store_true", help="不連接 ESP32")
    parser.add_argument("--no-sound", action="store_true", help="電腦不發出嗶聲與語音")
    parser.add_argument("--log", help="指定警示紀錄的檔名（批次分析用）")
    args = parser.parse_args()

    with open(resolve(args.config), encoding="utf-8") as f:
        cfg = json.load(f)

    if args.video:
        cap = cv2.VideoCapture(resolve(args.video))
        source_name = os.path.splitext(os.path.basename(args.video))[0]
    else:
        cam = cfg["camera"]
        cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(cam)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg["camera_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg["camera_height"])
        source_name = "camera"
    if not cap.isOpened():
        raise SystemExit("無法開啟影片或鏡頭，請檢查檔名或 config.json 的 camera")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30

    link = None if args.no_serial else Esp32Link(cfg.get("serial_port", "auto"), cfg.get("baud", 115200))
    use_pc_sound = not args.no_sound and not (link and link.ser)
    beeper = PcBeeper(cfg.get("pc_beep", True) and use_pc_sound)
    voice_on = cfg.get("voice", True)
    announcer = voice.Announcer(cfg.get("voice_cooldown_sec", 1.5), cfg.get("big_vehicle_classes", ["bus", "truck"]))
    pc_player = voice.PcPlayer(voice_on and use_pc_sound)
    voice_count = 0

    def play_clip(clip):
        if not voice_on:
            return
        if link and link.ser:
            link.send(f"P{clip}")
        else:
            pc_player.play(clip)
            beeper.quiet_until = time.time() + 1.5

    if voice_on and link and link.ser:
        link.send(f"V{int(cfg.get('voice_volume', 22))}")
    play_clip(voice.CLIP_READY)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.log:
        log_path = resolve(args.log)
    else:
        log_path = os.path.join(resolve(cfg.get("log_dir", "logs")), f"{source_name}_{stamp}.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_f = open(log_path, "w", newline="", encoding="utf-8-sig")
    log = csv.writer(log_f)
    log.writerow(["time", "event", "level", "vehicle", "track", "ttc_sec", "width_ratio", "voice"])

    snap_dir = None
    if cfg.get("snapshot_on_alert", True):
        snap_dir = os.path.join(resolve("output"), "snapshots", os.path.splitext(os.path.basename(log_path))[0])

    writer = None
    out_path = None
    model = YOLO(cfg["model"])
    vehicle_ids = set(cfg["vehicle_classes"])
    zone = cfg["zone_x"]
    tracker = Tracker(cfg)
    state = AlertState(cfg["hold_sec"])
    tracks, persons = [], []
    alert_count = danger_count = 0
    last_detect = -1e9
    last_send = 0.0
    shown_name, shown_ttc = "", None     # TFT 顯示的車種與秒數
    last_frame_wall = time.time()
    camera_lost_said = False
    frame_idx = 0
    now = 0.0
    view = None
    paused = False
    start = time.time()
    print("開始分析，按 Ctrl+C 或在視窗按 q 結束")

    try:
        while True:
            if not paused:
                ok, frame = cap.read()
                if not ok:
                    if args.video:
                        break
                    # 鏡頭斷線：停止送出燈號，ESP32 會自動顯示「離線」
                    if time.time() - last_frame_wall > 1.0 and not camera_lost_said:
                        print("鏡頭沒有畫面，請檢查 USB 線（ESP32 將顯示離線）")
                        camera_lost_said = True
                    time.sleep(0.05)
                    continue
                last_frame_wall = time.time()
                camera_lost_said = False
                now = frame_idx / fps if args.video else time.time() - start
                frame_idx += 1
                h, w = frame.shape[:2]
                snap_level = 0

                if now - last_detect >= cfg["detect_interval_sec"]:
                    last_detect = now
                    # agnostic_nms：同一台車不會同時被框成 bus 和 truck
                    res = model(frame, conf=cfg["confidence"], imgsz=cfg["imgsz"], agnostic_nms=True,
                                verbose=False)[0]
                    dets, persons = [], []
                    for b in res.boxes:
                        name = model.names[int(b.cls[0])]
                        box = tuple(int(v) for v in b.xyxy[0].tolist())
                        if name in vehicle_ids:
                            dets.append({"name": name, "box": box})
                        elif name == "person":
                            persons.append(box)
                    tracks = tracker.update(dets, now)

                    # 判斷每台車的逼近程度，取最危險的
                    want, worst = 0, None
                    for tr in tracks:
                        x1, y1, x2, y2 = tr.box
                        cx = (x1 + x2) / 2 / w
                        width_ratio = (x2 - x1) / w
                        tr.ttc = tr.estimate_ttc(cfg["min_points"])
                        tr.level = 0
                        if (not zone[0] <= cx <= zone[1] or tr.ttc is None
                                or width_ratio < cfg["min_width_ratio"] or tr.ttc >= cfg["ttc_warn"]):
                            tr.hits = 0
                            continue
                        tr.hits += 1
                        if tr.hits < cfg["confirm_count"]:
                            continue
                        tr.level = 2 if tr.ttc < cfg["ttc_danger"] else 1
                        if tr.level > want:
                            want, worst = tr.level, (tr, width_ratio)

                    event = state.update(want, now)
                    if worst:
                        shown_name, shown_ttc = worst[0].name, worst[0].ttc
                    elif not state.on:
                        shown_name, shown_ttc = "", None
                    if event in ("alert_on", "escalate"):
                        tr, wr = worst
                        log.writerow([round(now, 2), event, want, tr.name, tr.id, round(tr.ttc, 2), round(wr, 3), ""])
                        print(f"[{now:6.2f}s] {LEVEL_NAME[want]}：{tr.name} #{tr.id}，約 {tr.ttc:.1f} 秒後到達")
                        alert_count += event == "alert_on"
                        danger_count += want == 2
                        snap_level = want
                    elif event == "alert_off":
                        log.writerow([round(now, 2), "alert_off", 0, "", "", "", "", ""])
                        print(f"[{now:6.2f}s] 解除警示")

                    # 車種語音
                    alerting = [(tr.id, tr.name, tr.level) for tr in tracks if tr.level > 0]
                    said = announcer.update(now, alerting, state.level, event)
                    if said:
                        clip, text = said
                        play_clip(clip)
                        voice_count += 1
                        log.writerow([round(now, 2), "voice", state.level,
                                      "+".join(sorted({n for _, n, _ in alerting})),
                                      "+".join(str(i) for i, _, _ in alerting), "", "", text])
                        print(f"[{now:6.2f}s] 語音：{text}")
                    log_f.flush()

                # 燈號：畫面正常時每 0.2 秒送一次；ESP32 超過 1.5 秒沒收到會顯示「離線」
                if time.time() - last_send > 0.2:
                    last_send = time.time()
                    if link:
                        link.send(voice.status_line(state.level, shown_name, shown_ttc))
                beeper.update(state.level)

                view = frame.copy()
                if (args.save or snap_level) and cfg.get("privacy_blur", True):
                    blur_privacy(view, tracks, persons)
                draw_overlay(view, tracks, state.level, now, zone, source_name if args.video else "camera")
                if snap_level and snap_dir:
                    os.makedirs(snap_dir, exist_ok=True)
                    cv2.imwrite(os.path.join(snap_dir, f"t{now:07.2f}_L{snap_level}.jpg"), view)

                if args.save:
                    if writer is None:
                        os.makedirs(resolve("output"), exist_ok=True)
                        out_path = os.path.join(resolve("output"), f"{source_name}_{stamp}.mp4")
                        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                    writer.write(view)

            if args.window and view is not None:
                cv2.imshow("Rear Alert", view)
                key = cv2.waitKey(1 if not args.video else max(1, int(1000 / fps))) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord(" "):
                    paused = not paused
    except KeyboardInterrupt:
        pass
    finally:
        if state.on:
            log.writerow([round(now, 2), "alert_off", 0, "", "", "", "", ""])
        if link:
            link.send(voice.status_line(0, "", None))
        cap.release()
        if writer:
            writer.release()
            print("標註影片已存到：", out_path)
        cv2.destroyAllWindows()
        log_f.close()

        elapsed = max(1e-6, time.time() - start)
        summary = {
            "source": args.video or "camera",
            "duration_sec": round(now, 2),
            "frames": frame_idx,
            "processing_fps": round(frame_idx / elapsed, 1),
            "vehicles": dict(tracker.counts),
            "alerts": alert_count,
            "danger_alerts": danger_count,
            "voice_clips": voice_count,
            "config": {k: cfg[k] for k in ("model", "imgsz", "confidence", "zone_x", "min_width_ratio",
                                           "size_window_sec", "ttc_warn", "ttc_danger", "confirm_count",
                                           "hold_sec")},
        }
        with open(os.path.splitext(log_path)[0] + ".json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"長度 {summary['duration_sec']} 秒、警示 {alert_count} 次（危險 {danger_count} 次）、"
              f"處理速度 {summary['processing_fps']} 張/秒")
        print("紀錄已存到：", log_path)


if __name__ == "__main__":
    main()
