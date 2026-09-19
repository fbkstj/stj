"""步驟 2：調整「黃色」的判斷範圍，並記錄導盲磚淨空時的黃色比例（基準值）。

請在導盲磚「沒有被擋住」的時候執行。
操作：
  拖動滑桿   調整 H（色相）、S（飽和度）、V（亮度）的上下限
  s          儲存顏色範圍，並把目前的黃色比例存成基準值
  q / ESC    不儲存離開
"""
import cv2
import numpy as np

from common import load_config, open_source, roi_mask, save_config, scaled_roi, yellow_ratio

WINDOW = "Tune yellow - s=save, q=quit"
MASK_WINDOW = "Yellow mask (white = yellow)"


def main():
    cfg = load_config()
    cap, is_video = open_source(cfg)
    lo, hi = cfg["hsv_lower"], cfg["hsv_upper"]

    cv2.namedWindow(WINDOW)
    for name, value, maxv in [("H low", lo[0], 179), ("H high", hi[0], 179),
                              ("S low", lo[1], 255), ("S high", hi[1], 255),
                              ("V low", lo[2], 255), ("V high", hi[2], 255)]:
        cv2.createTrackbar(name, WINDOW, value, maxv, lambda v: None)

    first = None
    while True:
        ok, frame = cap.read()
        if not ok:
            if is_video:  # 影片播完就從頭再播
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            break
        if first is None:
            first = frame
        get = lambda n: cv2.getTrackbarPos(n, WINDOW)
        cfg["hsv_lower"] = [get("H low"), get("S low"), get("V low")]
        cfg["hsv_upper"] = [get("H high"), get("S high"), get("V high")]

        polygon = scaled_roi(cfg, frame.shape)
        if polygon is None:
            mask = np.full(frame.shape[:2], 255, dtype=np.uint8)
        else:
            mask = roi_mask(frame.shape, polygon)
        ratio = yellow_ratio(frame, mask, cfg)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        yellow = cv2.inRange(hsv, np.array(cfg["hsv_lower"]), np.array(cfg["hsv_upper"]))
        view = frame.copy()
        if polygon is not None:
            cv2.polylines(view, [polygon], True, (0, 255, 0), 2)
        cv2.putText(view, f"yellow in ROI: {ratio:.2f}   s=save q=quit", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow(WINDOW, view)
        cv2.imshow(MASK_WINDOW, cv2.bitwise_and(yellow, mask))

        key = cv2.waitKey(30) & 0xFF
        if key == ord("s"):
            cfg["baseline_yellow"] = round(ratio, 3)
            save_config(cfg)
            print(f"顏色範圍 {cfg['hsv_lower']} ~ {cfg['hsv_upper']}，基準黃色比例 {ratio:.3f}")
            break
        if key in (ord("q"), 27):
            print("未儲存")
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
