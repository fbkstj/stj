"""
測試現場警示盒：依序顯示每一種狀態，並檢查取消鈕。

用法：python test_alarm.py            自動尋找 ESP32
      python test_alarm.py COM5       指定序列埠

每個狀態維持 3 秒（警報倒數會從 5 數到 1），最後停止送訊號，約 1.5 秒後應顯示「未連線」。
測試期間按取消鈕，畫面會印出「收到取消鈕」。
"""
import sys
import time

from alarm_link import STATE_NAMES, AlarmLink, status_line

STEPS = [
    (0, None, "綠燈恆亮，TFT「監控中／畫面正常」"),
    (1, "倒地", "黃燈恆亮，TFT「注意／人員倒地／請留意監控畫面」"),
    (2, "持械", "紅燈快閃＋嗶聲，TFT「警報／疑似持械」與倒數數字"),
    (3, "持械", "紅燈恆亮、每 2 秒短嗶，TFT「已通報／已發送 LINE 通報」"),
    (4, "奔逃", "綠燈快閃，TFT「已取消／人群奔逃／已標記為誤報」"),
    (1, "聚集", "黃燈恆亮，TFT「注意／異常聚集」"),
    (0, None, "回到監控中"),
]


def hold(link, state, kind, seconds, sec_value=None):
    end = time.time() + seconds
    while time.time() < end:
        remain = sec_value if sec_value is not None else 0
        if state == 2:
            remain = max(1, int(end - time.time()) + 1)
        link.send(status_line(state, kind, remain))
        for msg in link.poll():
            if msg == "cancel":
                print("  → 收到取消鈕")
            elif msg == "ready":
                print("  → 警示盒重新開機完成")
        time.sleep(0.2)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = sys.argv[1] if len(sys.argv) > 1 else "auto"
    link = AlarmLink(port)
    if not link.connected:
        raise SystemExit("沒有連上警示盒：確認 USB 線、驅動程式（CP210x 或 CH340），或指定 COM 埠")
    print("開始測試，每個狀態 3 秒；可以隨時按取消鈕測試")
    for state, kind, expect in STEPS:
        code = status_line(state, kind, 5)
        print(f"{code}  {STATE_NAMES[state]}：{expect}")
        hold(link, state, kind, 5 if state == 2 else 3)
    print("停止送訊號：約 1.5 秒後應顯示「未連線」，綠燈每 2 秒閃一下")
    end = time.time() + 4
    while time.time() < end:
        for msg in link.poll():
            if msg == "cancel":
                print("  → 收到取消鈕")
        time.sleep(0.2)
    print("測試結束")


if __name__ == "__main__":
    main()
