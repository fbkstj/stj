"""步驟 1：在畫面上點出導盲磚的範圍，存到 config.json。

用法：
  python setup_roi.py                 使用 config.json 裡的來源（攝影機或影片）
  python setup_roi.py --time 5        影片來源時，改用第 5 秒的畫面

操作：
  滑鼠左鍵  依序點出導盲磚的四個角（或更多點）
  z         刪除上一個點
  c         全部清除
  s         儲存並離開
  q / ESC   不儲存離開
"""
import argparse

import cv2
import numpy as np

from common import load_config, open_source, save_config

WINDOW = "Setup ROI - click corners, s=save, z=undo, c=clear, q=quit"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--time", type=float, default=0.0, help="影片來源時使用第幾秒的畫面")
    args = parser.parse_args()

    cfg = load_config()
    cap, is_video = open_source(cfg)
    if is_video and args.time > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, args.time * 1000)
    frame = None
    for _ in range(10):  # 攝影機剛開啟時前幾張常常偏暗
        ok, img = cap.read()
        if ok:
            frame = img
        if is_video:
            break
    cap.release()
    if frame is None:
        raise RuntimeError("讀不到畫面")

    h, w = frame.shape[:2]
    points = [list(p) for p in (cfg.get("roi") or [])] if cfg.get("roi_frame_size") == [w, h] else []

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([x, y])

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, on_mouse)
    while True:
        view = frame.copy()
        if len(points) >= 3:
            overlay = view.copy()
            cv2.fillPoly(overlay, [np.array(points, dtype=np.int32)], (0, 200, 0))
            view = cv2.addWeighted(overlay, 0.35, view, 0.65, 0)
        for i, (x, y) in enumerate(points):
            cv2.circle(view, (x, y), 6, (0, 0, 255), -1)
            cv2.putText(view, str(i + 1), (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if len(points) >= 2:
            cv2.polylines(view, [np.array(points, dtype=np.int32)], len(points) >= 3, (0, 255, 0), 2)
        cv2.putText(view, f"points: {len(points)}  s=save z=undo c=clear q=quit", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow(WINDOW, view)
        key = cv2.waitKey(30) & 0xFF
        if key == ord("z") and points:
            points.pop()
        elif key == ord("c"):
            points.clear()
        elif key == ord("s"):
            if len(points) < 3:
                print("至少要點 3 個點")
                continue
            cfg["roi"] = points
            cfg["roi_frame_size"] = [w, h]
            save_config(cfg)
            break
        elif key in (ord("q"), 27):
            print("未儲存")
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
