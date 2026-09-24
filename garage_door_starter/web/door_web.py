# -*- coding: utf-8 -*-
"""
地下室鐵捲門 · 網頁控制台（在電腦端執行）

為什麼要有這支程式：
  1. 瀏覽器不能直接播 RTSP，這裡把 RTSP 轉成 MJPEG 餵給 <img>。
  2. 這個 broker 沒開 WebSocket，網頁沒辦法自己連 MQTT，由這裡代發。
  3. 帳號密碼留在電腦端，不會出現在網頁原始碼裡。

執行：
  python door_web.py        （需要 opencv-python 與 paho-mqtt）
  然後用瀏覽器開 http://localhost:8000 （同區網的手機用電腦的 IP）
"""
import os
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")  # 要在 import cv2 前設

import json
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import cv2
import paho.mqtt.client as mqtt

from settings import (CAMERA_RTSP, HTTP_PORT, LOGIN_PASSWORD, MQTT_HOST, MQTT_PASS,
                      MQTT_PORT, MQTT_USER, TOPIC_AVAIL, TOPIC_CLOSE, TOPIC_LOG,
                      TOPIC_OPEN, TOPIC_PAUSE, TOPIC_STATE)

HERE = Path(__file__).parent
CMD_TOPICS = {"open": TOPIC_OPEN, "pause": TOPIC_PAUSE, "close": TOPIC_CLOSE}
CMD_NAMES = {"open": "開門", "pause": "停止", "close": "關門"}
MIN_GAP_SEC = 2.0          # 同一個指令兩次之間至少間隔這麼久（和韌體的去彈跳一致）


# ---------------- MQTT（帳密只存在這支程式裡） ----------------
class DoorMqtt:
    def __init__(self):
        self.state = {"avail": "unknown", "state": "unknown", "log": ""}
        self.last_sent = {}
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect_async(MQTT_HOST, MQTT_PORT, 30)
        self.client.loop_start()

    def _on_connect(self, c, u, flags, rc, props=None):
        print(f"[MQTT] 連線 {MQTT_HOST}:{MQTT_PORT} → {rc}")
        for t in (TOPIC_AVAIL, TOPIC_STATE, TOPIC_LOG):
            c.subscribe(t)

    def _on_message(self, c, u, msg):
        body = msg.payload.decode("utf-8", "replace")
        if msg.topic == TOPIC_AVAIL:
            self.state["avail"] = body or "unknown"
        elif msg.topic == TOPIC_STATE:
            self.state["state"] = body or "unknown"
        elif msg.topic == TOPIC_LOG:
            self.state["log"] = f"{time.strftime('%H:%M:%S')} {body}"

    def send(self, cmd):
        """回傳 (成功, 訊息)。擋掉連點，並在離線時直接拒絕。"""
        if cmd not in CMD_TOPICS:
            return False, "不認識的指令"
        if self.state["avail"] != "online":
            return False, "鐵捲門控制器不在線上，指令沒有送出"
        now = time.monotonic()
        if now - self.last_sent.get(cmd, 0) < MIN_GAP_SEC:
            return False, "剛剛才送過同一個指令，請稍等一下"
        if not self.client.is_connected():
            return False, "電腦這端還沒連上 MQTT"
        self.client.publish(CMD_TOPICS[cmd], "web", qos=1)
        self.last_sent[cmd] = now
        print(f"[指令] {CMD_NAMES[cmd]} 已送出")
        return True, f"{CMD_NAMES[cmd]} 指令已送出"


# ---------------- 攝影機：RTSP → MJPEG ----------------
class Camera:
    """背景執行緒持續讀取 RTSP，網頁要畫面時拿最新一張，讀不到就回報錯誤訊息。"""

    def __init__(self, url):
        self.url = url
        self.frame = None
        self.error = "尚未連線"
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                with self.lock:
                    self.error = "連不到攝影機（先確認電腦 ping 得到它，路由器的 IoT 隔離常是元凶）"
                cap.release()
                time.sleep(5)
                continue
            with self.lock:
                self.error = ""
            print("[攝影機] 已連線")
            fails = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if fails > 30:
                        break
                    time.sleep(0.05)
                    continue
                fails = 0
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ok:
                    with self.lock:
                        self.frame = buf.tobytes()
            cap.release()
            with self.lock:
                self.error = "串流中斷，重新連線中"
            print("[攝影機] 串流中斷，5 秒後重連")
            time.sleep(5)

    def snapshot(self):
        with self.lock:
            return self.frame, self.error


# ---------------- HTTP ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "DoorWeb/1.0"

    def log_message(self, fmt, *args):
        pass                                    # 不要洗畫面

    # --- 小工具 ---
    def _send(self, code, ctype, body, extra=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _authed(self):
        if not LOGIN_PASSWORD:
            return True
        return f"door_pw={LOGIN_PASSWORD}" in (self.headers.get("Cookie") or "")

    # --- 路由 ---
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/login":
            self._send(200, "text/html; charset=utf-8", (HERE / "login.html").read_bytes())
            return

        if not self._authed():
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        if path == "/":
            self._send(200, "text/html; charset=utf-8", (HERE / "index.html").read_bytes())
        elif path == "/status":
            frame, err = camera.snapshot()
            self._json({**door.state, "camera_ok": frame is not None, "camera_error": err})
        elif path == "/stream.mjpg":
            self._stream()
        else:
            self._send(404, "text/plain; charset=utf-8", "找不到".encode("utf-8"))

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/login":
            n = int(self.headers.get("Content-Length") or 0)
            pw = json.loads(self.rfile.read(n) or b"{}").get("password", "")
            if LOGIN_PASSWORD and pw != LOGIN_PASSWORD:
                time.sleep(1)                   # 稍微拖慢暴力猜測
                self._json({"ok": False, "msg": "密碼不對"}, 401)
                return
            self._send(200, "application/json; charset=utf-8", b'{"ok":true}',
                       extra=[("Set-Cookie", f"door_pw={LOGIN_PASSWORD}; Path=/; Max-Age=2592000; SameSite=Strict")])
            return

        if not self._authed():
            self._json({"ok": False, "msg": "請先登入"}, 401)
            return

        if path.startswith("/cmd/"):
            ok, msg = door.send(path[len("/cmd/"):])
            self._json({"ok": ok, "msg": msg})
        else:
            self._json({"ok": False, "msg": "找不到"}, 404)

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                frame, _ = camera.snapshot()
                if frame:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     + f"Content-Length: {len(frame)}\r\n\r\n".encode() + frame + b"\r\n")
                time.sleep(0.1)                 # 約 10 fps，夠看門開了沒
        except (BrokenPipeError, ConnectionResetError):
            pass                                # 使用者關掉分頁，正常現象


if __name__ == "__main__":
    door = DoorMqtt()
    camera = Camera(CAMERA_RTSP)
    srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"\n鐵捲門控制台：http://localhost:{HTTP_PORT}")
    print("同一個 Wi-Fi 下的手機請改用這台電腦的區網 IP 加上同一個埠")
    print("按 Ctrl+C 結束\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n結束")
