"""製作「略過」按鈕的樣板圖片（YouTube 改版、語言不同，或按鈕認不到時使用）。

步驟：
  1. 在 YouTube 播放影片，等到畫面出現「略過」按鈕
  2. 執行這支程式，5 秒內切回 YouTube 視窗
  3. 程式截圖後會開一個視窗，用滑鼠框出「略過」按鈕，按 Enter 確認（按 c 取消）
  4. 圖片存到 templates/，下次啟動 airtouch.py 就會一起比對

用法：python make_skip_template.py
      python make_skip_template.py --delay 8
"""
import argparse
import datetime as dt
import os
import time

import cv2
import numpy as np
from PIL import ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=int, default=5, help="截圖前等待幾秒")
    args = parser.parse_args()
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    for i in range(args.delay, 0, -1):
        print(f"{i} 秒後截圖，請切到 YouTube 視窗…")
        time.sleep(1)
    shot = cv2.cvtColor(np.array(ImageGrab.grab(all_screens=True)), cv2.COLOR_RGB2BGR)

    scale = min(1.0, 1400 / shot.shape[1])
    small = cv2.resize(shot, None, fx=scale, fy=scale)
    x, y, w, h = cv2.selectROI("框出略過按鈕後按 Enter", small, showCrosshair=False)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        print("沒有框選，取消")
        return
    x, y, w, h = [int(v / scale) for v in (x, y, w, h)]
    crop = cv2.cvtColor(shot[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)

    os.makedirs(os.path.join(HERE, "templates"), exist_ok=True)
    out = os.path.join(HERE, "templates", f"skip_{dt.datetime.now():%Y%m%d_%H%M%S}.png")
    ok, buf = cv2.imencode(".png", crop)          # 用 imencode＋tofile，資料夾有中文也能存
    buf.tofile(out)
    print(f"已存 {w}×{h} 的樣板：{out}")


if __name__ == "__main__":
    main()
