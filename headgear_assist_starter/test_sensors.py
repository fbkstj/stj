"""測試 ESP32、ToF 測距與震動馬達。

用法：python test_sensors.py            自動尋找 ESP32
      python test_sensors.py COM5       指定序列埠
畫面會持續顯示左右距離；按 Enter 讓兩顆馬達各震一下，輸入 q 再按 Enter 離開。
請用手或書本在帽簷前方 0.3～2 公尺間移動，確認距離與震動節奏會跟著改變。
"""
import sys
import threading
import time

import serial
from serial.tools import list_ports


def find_port():
    keys = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "usb jtag", "uart")
    ports = list(list_ports.comports())
    for p in ports:
        print("找到序列埠：", p.device, p.description)
    for p in ports:
        if any(k in f"{p.description} {p.manufacturer or ''}".lower() for k in keys):
            return p.device
    return None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    if not port:
        raise SystemExit("找不到 ESP32，請確認 USB 線與驅動程式（CP210x 或 CH340）")
    ser = serial.Serial(port, 115200, timeout=1)
    print("已連線：", port, "（ESP32 重新開機需要約 2 秒）")
    stop = False

    def reader():
        while not stop:
            line = ser.readline().decode("ascii", "ignore").strip()
            if line.startswith("D,"):
                _, l, r = line.split(",")
                print(f"\r左 {l:>5} mm   右 {r:>5} mm   ", end="", flush=True)
            elif line:
                print("\n收到：", line)

    threading.Thread(target=reader, daemon=True).start()
    while True:
        cmd = input()
        if cmd.strip().lower() == "q":
            break
        ser.write(b"T")
        print("已送出馬達測試")
    stop = True
    time.sleep(0.2)
    ser.close()


if __name__ == "__main__":
    main()
