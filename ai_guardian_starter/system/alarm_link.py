"""
現場警示盒（ESP32）：決定要顯示的狀態，並透過 USB 序列埠傳送。

電腦 → ESP32（每 0.2 秒一次，4 個字元＋換行）：
  S<狀態><事件><秒數>
    狀態  0 監控中  1 注意（中、低風險事件）  2 警報倒數  3 已通報  4 已取消
    事件  W 持械  R 奔逃  F 倒地  C 聚集  N 無
    秒數  警報倒數剩幾秒（0～9），其他狀態填 0
  例：S2W4 ＝ 持械警報，4 秒後發出通報

ESP32 → 電腦：
  I,ready   開機完成
  K         保全按下取消鈕（等於在監控牆按 C）

ESP32 超過 1.5 秒沒收到狀態，會自己顯示「未連線」。
"""
import math
import time

KIND_CODE = {"持械": "W", "奔逃": "R", "倒地": "F", "聚集": "C"}
STATE_NAMES = ["監控中", "注意", "警報倒數", "已通報", "已取消"]

NOTICE_SHOW_SEC = 3       # 中、低風險事件顯示「注意」多久
REPORTED_SHOW_SEC = 10    # 通報後顯示「已通報」多久
CANCELLED_SHOW_SEC = 3    # 取消後顯示「已取消」多久


def status_line(state, kind=None, sec=0):
    code = KIND_CODE.get(kind, "N")
    sec = max(0, min(9, int(sec)))
    if state != 2:
        sec = 0
    return f"S{state}{code}{sec}"


def compute_state(alerter, now):
    """依通報模組的狀態決定警示盒要顯示什麼，優先順序：警報倒數 > 已通報 > 已取消 > 注意 > 監控中。"""
    if alerter.pending:
        p = min(alerter.pending, key=lambda p: p["deadline"])
        remain = max(0.0, p["deadline"] - now)
        return 2, p["ev"].kind, math.ceil(remain)
    for state, attr, show in ((3, "last_reported", REPORTED_SHOW_SEC),
                              (4, "last_cancelled", CANCELLED_SHOW_SEC),
                              (1, "last_notice", NOTICE_SHOW_SEC)):
        rec = getattr(alerter, attr, None)
        if rec and now - rec[0] < show:
            return state, rec[1], 0
    return 0, None, 0


def parse_line(text):
    """ESP32 傳來的一行 → 'cancel'、'ready' 或 None。"""
    text = text.strip()
    if text == "K":
        return "cancel"
    if text.startswith("I,ready"):
        return "ready"
    return None


class AlarmLink:
    """沒有 pyserial 或找不到 ESP32 時，send() 與 poll() 什麼都不做，主程式照常執行。"""

    def __init__(self, port="auto", baud=115200):
        self.ser = None
        self.buf = b""
        self.last_send = 0.0
        if not port or port == "none":
            return
        try:
            import serial
            from serial.tools import list_ports
        except ImportError:
            print("[警示盒] 尚未安裝 pyserial（pip install pyserial），先不使用警示盒")
            return
        if port == "auto":
            keys = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "usb jtag", "uart")
            port = next((p.device for p in list_ports.comports()
                         if any(k in f"{p.description} {p.manufacturer or ''}".lower() for k in keys)), None)
            if not port:
                print("[警示盒] 找不到 ESP32，先不使用警示盒（可用 --serial COM3 指定）")
                return
        try:
            self.ser = serial.Serial(port, baud, timeout=0)
            time.sleep(2)            # ESP32 連線時會重新開機
            print(f"[警示盒] 已連線 {port}")
        except Exception as e:
            print(f"[警示盒] 無法開啟 {port}：{e}")

    @property
    def connected(self):
        return self.ser is not None

    def send(self, text):
        if not self.ser:
            return False
        try:
            self.ser.write(f"{text}\n".encode("ascii"))
            return True
        except Exception as e:
            print(f"[警示盒] 寫入失敗，警示盒會顯示未連線：{e}")
            self.ser = None
            return False

    def update(self, alerter, now, interval=0.2):
        """主迴圈每一輪呼叫：定時送出狀態。"""
        if self.ser and now - self.last_send >= interval:
            self.last_send = now
            self.send(status_line(*compute_state(alerter, now)))

    def poll(self):
        """讀取 ESP32 傳來的訊息，回傳 ['cancel', ...]。"""
        if not self.ser:
            return []
        try:
            self.buf += self.ser.read(256)
        except Exception as e:
            print(f"[警示盒] 讀取失敗：{e}")
            self.ser = None
            return []
        out = []
        while b"\n" in self.buf:
            raw, self.buf = self.buf.split(b"\n", 1)
            msg = parse_line(raw.decode("ascii", errors="ignore"))
            if msg:
                out.append(msg)
        self.buf = self.buf[-64:]
        return out
