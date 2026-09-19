"""步驟 3：導盲磚占用偵測主程式。

判斷方式（兩個訊號，任一成立就算「被占用」）：
  1. 車輛：YOLO 偵測到機車、腳踏車等，且車輛「下半部」（輪子著地處）有一定比例落在導盲磚區域內
  2. 遮擋：導盲磚區域看得到的黃色比例，低於淨空時基準值的一定比例（可抓到雜物、看板等 YOLO 不認得的東西）

「被占用」持續超過 occupy_seconds 秒才算一次事件，避免行人或車輛經過就誤報；
淨空超過 clear_seconds 秒才算事件結束。

用法：
  python paving_monitor.py                         使用 config.json 的來源
  python paving_monitor.py --source test.mp4       指定影片
  python paving_monitor.py --no-window             不開視窗（批次測試用）
按 q 或 ESC 離開。
"""
import argparse
import csv
import datetime as dt
import json
import os
import threading
import time
import urllib.request

import cv2
from ultralytics import YOLO

from common import HERE, load_config, open_source, roi_mask, scaled_roi, yellow_ratio


# ---------- 提醒輸出 ----------
def speak(text):
    """用電腦喇叭念出提醒（背景執行，不會卡住畫面）。"""
    def run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:  # 沒裝 pyttsx3 或沒有中文語音時，改用嗶聲
            print("語音播放失敗，改用嗶聲：", e)
            try:
                import winsound
                winsound.Beep(1000, 600)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def line_push(text):
    """用 LINE Messaging API 推播文字（LINE Notify 已停止服務）。
    權杖與收件者 ID 放在環境變數，不要寫進程式或上傳到網路：
      LINE_CHANNEL_TOKEN、LINE_TO
    """
    token, to = os.environ.get("LINE_CHANNEL_TOKEN"), os.environ.get("LINE_TO")
    if not token or not to:
        print("未設定 LINE_CHANNEL_TOKEN / LINE_TO，略過 LINE 通知")
        return

    def run():
        body = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
        req = urllib.request.Request("https://api.line.me/v2/bot/message/push", data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print("LINE 通知已送出：", resp.status)
        except Exception as e:
            print("LINE 通知失敗：", e)
    threading.Thread(target=run, daemon=True).start()


class SerialAlert:
    """選配：透過 USB 序列埠通知 ESP32 亮燈或響蜂鳴器（送出 A=警示、C=解除）。"""
    def __init__(self, port):
        self.ser = None
        if not port:
            return
        try:
            import serial
            self.ser = serial.Serial(port, 115200, timeout=1)
            print("已連線 ESP32：", port)
        except Exception as e:
            print("無法開啟序列埠，略過 ESP32：", e)

    def send(self, ch):
        if self.ser:
            try:
                self.ser.write(ch.encode())
            except Exception as e:
                print("序列埠傳送失敗：", e)


# ---------- 影像處理 ----------
def blur_privacy(img, boxes, names):
    """截圖存檔前，把行人與車輛下半部（車牌位置）打上馬賽克，保護隱私。"""
    out = img.copy()
    h, w = out.shape[:2]
    for (x1, y1, x2, y2), cls in boxes:
        name = names[cls]
        if name == "person":
            ya = y1
        elif name in ("car", "truck", "bus", "motorcycle", "bicycle"):
            ya = int(y2 - (y2 - y1) * 0.45)
        else:
            continue
        x1c, x2c = max(0, x1), min(w, x2)
        ya, y2c = max(0, ya), min(h, y2)
        if x2c - x1c > 2 and y2c - ya > 2:
            roi = out[ya:y2c, x1c:x2c]
            rh, rw = roi.shape[:2]
            small = cv2.resize(roi, (max(1, rw // 16), max(1, rh // 16)), interpolation=cv2.INTER_LINEAR)
            out[ya:y2c, x1c:x2c] = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
    return out


def bottom_overlap(box, mask):
    """車輛框「下 35%」落在導盲磚區域內的比例。"""
    x1, y1, x2, y2 = box
    h, w = mask.shape[:2]
    yb = int(y2 - (y2 - y1) * 0.35)
    x1, x2 = max(0, x1), min(w, x2)
    yb, y2 = max(0, yb), min(h, y2)
    area = (x2 - x1) * (y2 - yb)
    if area <= 0:
        return 0.0
    return cv2.countNonZero(mask[yb:y2, x1:x2]) / float(area)


def fmt_time(t, is_video):
    return f"{t:.1f}" if is_video else dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="攝影機編號或影片檔（不填就用 config.json）")
    parser.add_argument("--config", help="設定檔路徑（預設 config.json）")
    parser.add_argument("--no-window", action="store_true", help="不顯示視窗")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else load_config()
    cap, is_video = open_source(cfg, args.source)
    show = cfg.get("show_window", True) and not args.no_window

    out_dir = os.path.join(HERE, cfg.get("output_dir", "output"))
    snap_dir = os.path.join(out_dir, "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    events_path = os.path.join(out_dir, "events.csv")
    state_path = os.path.join(out_dir, "state_log.csv")
    new_events = not os.path.exists(events_path)
    events_f = open(events_path, "a", newline="", encoding="utf-8-sig")
    events_w = csv.writer(events_f)
    if new_events:
        events_w.writerow(["event_id", "start", "end", "duration_sec", "cause",
                           "max_overlap", "min_yellow_ratio", "snapshot"])
    state_f = open(state_path, "w", newline="", encoding="utf-8-sig")
    state_w = csv.writer(state_f)
    state_w.writerow(["time", "occupied", "alert", "yellow_ratio", "cause"])

    print("載入模型：", cfg["model"], "（第一次執行會自動下載）")
    model = YOLO(cfg["model"])
    names = model.names
    vehicle_ids = {i for i, n in names.items() if n in cfg["vehicle_classes"]}
    serial_alert = SerialAlert(cfg.get("serial_port"))

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_idx = 0
    polygon = mask = None
    baseline = cfg.get("baseline_yellow")
    auto_baseline = baseline is None
    boxes, last_detect = [], -1e9
    occ_start = last_occ = None
    alert_active = False
    event = {}
    event_id = 0
    last_logged_sec = None
    overlap_now, cause_now = 0.0, ""

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_idx / fps if is_video else time.time()
            frame_idx += 1

            if polygon is None:
                polygon = scaled_roi(cfg, frame.shape)
                if polygon is None:
                    raise RuntimeError("還沒設定導盲磚區域，請先執行 setup_roi.py")
                mask = roi_mask(frame.shape, polygon)

            # 物件偵測（每 detect_interval_sec 秒做一次，減輕 CPU 負擔）
            if t - last_detect >= cfg.get("detect_interval_sec", 0.5):
                last_detect = t
                res = model(frame, conf=cfg["confidence"], verbose=False)[0]
                boxes = [([int(v) for v in b.xyxy[0].tolist()], int(b.cls[0])) for b in res.boxes]

            ratio = yellow_ratio(frame, mask, cfg)
            if auto_baseline:  # 沒有先校正時，用看過最清楚的畫面當基準
                baseline = max(baseline or 0.0, ratio)

            overlap_now, cause_now = 0.0, ""
            for box, cls in boxes:
                if cls in vehicle_ids:
                    ov = bottom_overlap(box, mask)
                    if ov > overlap_now:
                        overlap_now, cause_now = ov, names[cls]
            vehicle_hit = overlap_now >= cfg["overlap_threshold"]
            blocked = bool(baseline) and baseline > 0.05 and ratio < baseline * cfg["blocked_ratio"]
            occupied_now = vehicle_hit or blocked
            if not vehicle_hit and blocked:
                cause_now = "blocked"

            # 狀態機：持續占用才發出警示，淨空一段時間才解除
            if occupied_now:
                if occ_start is None:
                    occ_start = t
                    event = {"max_overlap": 0.0, "min_ratio": 1.0, "causes": set()}
                last_occ = t
                event["max_overlap"] = max(event["max_overlap"], overlap_now)
                event["min_ratio"] = min(event["min_ratio"], ratio)
                event["causes"].add(cause_now)
                if not alert_active and t - occ_start >= cfg["occupy_seconds"]:
                    alert_active = True
                    event_id += 1
                    snap = ""
                    if cfg.get("save_snapshots", True):
                        img = blur_privacy(frame, boxes, names) if cfg.get("blur_privacy", True) else frame
                        cv2.polylines(img, [polygon], True, (0, 0, 255), 3)
                        snap = f"snapshots/event_{event_id:04d}_{int(time.time())}.jpg"
                        cv2.imwrite(os.path.join(out_dir, snap), img)
                    event["snapshot"] = snap
                    msg = f"導盲磚被占用（{cause_now}），已持續 {int(t - occ_start)} 秒"
                    print(f"[警示] {fmt_time(t, is_video)} {msg}")
                    if cfg.get("voice_alert", True):
                        speak(cfg.get("voice_text", "此處為導盲磚，請勿停放車輛"))
                    if cfg.get("line_push"):
                        line_push(msg)
                    serial_alert.send("A")
            elif occ_start is not None and t - last_occ >= cfg["clear_seconds"]:
                if alert_active:
                    causes = sorted(c for c in event["causes"] if c)
                    events_w.writerow([event_id, fmt_time(occ_start, is_video), fmt_time(last_occ, is_video),
                                       round(last_occ - occ_start, 1), "+".join(causes),
                                       round(event["max_overlap"], 2), round(event["min_ratio"], 3),
                                       event.get("snapshot", "")])
                    events_f.flush()
                    print(f"[解除] {fmt_time(t, is_video)} 事件 {event_id} 結束")
                    serial_alert.send("C")
                occ_start = last_occ = None
                alert_active = False

            # 每秒記錄一次狀態，給 evaluate.py 計算準確率
            sec = int(t)
            if sec != last_logged_sec:
                last_logged_sec = sec
                state_w.writerow([sec if is_video else fmt_time(t, False),
                                  int(occ_start is not None), int(alert_active),
                                  round(ratio, 3), cause_now])

            if show:
                view = frame.copy()
                color = (0, 0, 255) if alert_active else ((0, 165, 255) if occ_start is not None else (0, 200, 0))
                overlay = view.copy()
                cv2.fillPoly(overlay, [polygon], color)
                view = cv2.addWeighted(overlay, 0.25, view, 0.75, 0)
                cv2.polylines(view, [polygon], True, color, 2)
                for (x1, y1, x2, y2), cls in boxes:
                    c = (0, 0, 255) if cls in vehicle_ids else (200, 200, 200)
                    cv2.rectangle(view, (x1, y1), (x2, y2), c, 2)
                    cv2.putText(view, names[cls], (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
                if alert_active:
                    status = f"ALERT {int(t - occ_start)}s ({cause_now or '...'})"
                elif occ_start is not None:
                    status = f"OCCUPIED {int(t - occ_start)}s / {cfg['occupy_seconds']}s"
                else:
                    status = "CLEAR"
                base_txt = f"{baseline:.2f}" if baseline else "-"
                cv2.rectangle(view, (0, 0), (view.shape[1], 40), (0, 0, 0), -1)
                cv2.putText(view, f"{status} | yellow {ratio:.2f} (base {base_txt}) | overlap {overlap_now:.2f}",
                            (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                cv2.imshow("Tactile Paving Monitor - q to quit", view)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    finally:
        if alert_active:  # 結束時事件還沒解除，也要記錄下來
            causes = sorted(c for c in event["causes"] if c)
            events_w.writerow([event_id, fmt_time(occ_start, is_video), fmt_time(last_occ, is_video),
                               round(last_occ - occ_start, 1), "+".join(causes),
                               round(event["max_overlap"], 2), round(event["min_ratio"], 3),
                               event.get("snapshot", "")])
        events_f.close()
        state_f.close()
        cap.release()
        cv2.destroyAllWindows()
        print("紀錄已存到：", out_dir)


if __name__ == "__main__":
    main()
