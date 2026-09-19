"""測試 ESP32 的燈號、蜂鳴器、TFT 文字與 DFPlayer 語音。

步驟：
  1. 燈號與 TFT：安全 → 注意（機車 3.5 秒）→ 注意（汽車 2.8 秒）→ 危險（大型車 1.2 秒），各 3 秒
  2. 語音：依序播放 001～009 號語音（沒插 microSD 卡或接線錯誤就不會有聲音）
  3. 停止傳送：約 1.5 秒後應該變成「離線」（綠燈慢閃、TFT 顯示未連線）

用法：python test_lights.py          自動尋找序列埠
      python test_lights.py COM5
      python test_lights.py --no-voice   只測燈號與 TFT
"""
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    raise SystemExit("尚未安裝 pyserial：pip install pyserial")

from voice import CLIPS

KEYS = ("cp210", "ch340", "ch910", "silicon labs", "usb serial", "usb-serial", "usb jtag", "uart")

STEPS = [
    ("S0N00", "安全：綠燈恆亮；TFT 綠色「安全」、「後方無來車」"),
    ("S1M35", "注意：黃燈閃、每秒嗶一聲；TFT 黃色「注意」、「後方機車」、3.5 秒後到達"),
    ("S1C28", "注意：TFT 改成「後方汽車」、2.8 秒後到達"),
    ("S2B12", "危險：紅燈快閃、連續嗶聲；TFT 紅色「危險」、「後方大型車」、1.2 秒後到達"),
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    voice_test = "--no-voice" not in sys.argv
    port = args[0] if args else next(
        (p.device for p in list_ports.comports()
         if any(k in f"{p.description} {p.manufacturer or ''}".lower() for k in KEYS)), None)
    if not port:
        print("找不到 ESP32。目前的序列埠：")
        for p in list_ports.comports():
            print("  ", p.device, p.description)
        raise SystemExit("請確認 USB 線，或指定序列埠，例如：python test_lights.py COM5")

    with serial.Serial(port, 115200, timeout=0.1) as ser:
        print("已連線", port, "，等待 ESP32 重新開機…")
        time.sleep(2.5)
        print("ESP32 回應：", ser.read(200).decode("ascii", "ignore").strip() or "（沒有）")

        def hold(status, seconds):
            end = time.time() + seconds
            while time.time() < end:
                ser.write(f"{status}\n".encode())
                time.sleep(0.2)

        print("\n=== 1. 燈號與 TFT ===")
        for status, text in STEPS:
            print(f"{status}  {text}")
            hold(status, 3)

        if voice_test:
            print("\n=== 2. 語音（DFPlayer）===")
            ser.write(b"V22\n")
            for n, text in CLIPS.items():
                print(f"P{n}  {text}")
                ser.write(f"P{n}\n".encode())
                hold("S0N00", 1.8)

        print("\n=== 3. 離線 ===")
        print("停止傳送：約 1.5 秒後應該變成「離線」（綠燈慢閃、TFT 顯示未連線）")
        time.sleep(3)
    print("測試完成")


if __name__ == "__main__":
    main()
