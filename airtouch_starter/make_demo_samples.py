"""產生練習用的手勢樣本 data/demo_samples.csv（還沒收集自己的樣本前，先用它練習評估流程）。

做法：先畫一隻「標準手」的 21 個關節點，依手勢把手指伸直或彎曲，
再隨機旋轉、縮放、移動、左右翻轉、加上抖動，模擬不同人、不同角度與距離。
約兩成是「困難樣本」（標籤 demo_hard）：角度偏到 ±50 度、抖動加大，用來觀察方法的極限。
樣本格式和 collect_samples.py 收集的一樣，可以直接用 evaluate_gestures.py 評估。

注意：這是用數學畫出來的手，比真實的手整齊很多，成績一定比較好看；
報告裡的準確率要用自己收集的樣本。

用法：python make_demo_samples.py
"""
import csv
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 640, 480
PER_LABEL = 150

MCP = {"index": (-0.35, -1.0), "middle": (-0.1, -1.05), "ring": (0.15, -1.0), "pinky": (0.38, -0.9)}
SEGMENTS = {"index": (0.45, 0.28, 0.22), "middle": (0.5, 0.3, 0.24), "ring": (0.47, 0.28, 0.22), "pinky": (0.37, 0.22, 0.2)}
FAN = {"index": -8, "middle": 0, "ring": 7, "pinky": 15}         # 伸直時的張開角度
ORDER = ["index", "middle", "ring", "pinky"]


def unit(deg):
    """方向角（0＝右、90＝上）→ 畫面座標的單位向量（y 朝下）。"""
    r = math.radians(deg)
    return np.array([math.cos(r), -math.sin(r)])


def finger(name, extended, fan=None):
    base = np.array(MCP[name])
    ang = 90 - (FAN[name] if fan is None else fan)
    pts = [base]
    bends = (0, 0, 0) if extended else (0, -100, -70)            # 彎曲：往手掌內折
    for seg, bend in zip(SEGMENTS[name], bends):
        ang += bend
        pts.append(pts[-1] + unit(ang) * seg)
    return pts                                                     # 指根、第二關節、第三關節、指尖


def thumb(extended):
    cmc, mcp = np.array([-0.35, -0.25]), np.array([-0.6, -0.45])
    if extended:
        d = (mcp - cmc) / np.linalg.norm(mcp - cmc)
        ip = mcp + d * 0.35
        return [cmc, mcp, ip, ip + d * 0.3]
    return [cmc, mcp, np.array([-0.45, -0.72]), np.array([-0.22, -0.8])]


def hand(ext, thumb_ext, fans=None):
    pts = [np.array([0.0, 0.0])] + thumb(thumb_ext)
    for i, name in enumerate(ORDER):
        pts += finger(name, ext[i], (fans or {}).get(name))
    return np.array(pts)


def rotate(pts, deg):
    """以手腕為中心轉 deg 度（正值＝逆時針，和方向角一致）。"""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    x, y = pts[:, 0], -pts[:, 1]
    return np.stack([x * c - y * s, -(x * s + y * c)], axis=1)


def pose(label, rng, hard=False):
    """回傳 (關節點, 旋轉角度, 可以左右翻轉嗎)。hard＝角度偏得比較多的困難樣本。"""
    jitter = rng.uniform(-50, 50) if hard else rng.uniform(-25, 25)
    if label == "open_palm":
        return hand([1, 1, 1, 1], True), jitter, True
    if label == "v_sign":
        return hand([1, 1, 0, 0], False, {"index": -12, "middle": 10}), jitter, True
    if label == "fist":
        return hand([0, 0, 0, 0], False), jitter, True
    if label in ("point_right", "point_left"):
        p = hand([1, 0, 0, 0], False, {"index": 0})
        return p, (-90 if label == "point_right" else 90) + jitter, False
    if label in ("thumb_up", "thumb_down"):
        p = hand([0, 0, 0, 0], True)
        d = p[4] - p[2]
        now = math.degrees(math.atan2(-d[1], d[0]))
        target = 90 if label == "thumb_up" else -90
        return p, target - now + jitter, False
    # none：不是指令的手勢
    kind = rng.integers(4)
    if kind == 0:
        return hand([1, 1, 1, 0], False), jitter, True             # 三根手指
    if kind == 1:
        return hand([0, 0, 0, 1], False), jitter, True             # 只有小指
    if kind == 2:
        return hand([1, 0, 0, 0], False, {"index": 0}), jitter, True   # 食指朝上
    return hand([1, 1, 0, 0], False, {"index": -2, "middle": 2}), jitter, True   # 兩指併攏


def main():
    rng = np.random.default_rng(0)
    labels = ["open_palm", "point_right", "point_left", "thumb_up", "thumb_down", "v_sign", "fist", "none", "too_far"]
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    out = os.path.join(HERE, "data", "demo_samples.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["label", "tag", "width", "height"] + [f"{a}{i}" for i in range(21) for a in "xy"])
        for label in labels:
            for k in range(PER_LABEL):
                hard = rng.random() < 0.2
                if label == "too_far":
                    pts, ang, flip = pose("open_palm", rng)
                    palm = rng.uniform(15, 40)
                else:
                    pts, ang, flip = pose(label, rng, hard)
                    palm = rng.uniform(60, 160)
                pts = rotate(pts, ang)
                if flip and rng.random() < 0.5:
                    pts[:, 0] *= -1                                  # 左手
                pts = pts * palm / np.linalg.norm(pts[9] - pts[0])
                pts += rng.normal(0, (0.06 if hard else 0.02) * palm, pts.shape)   # 關節點抖動
                lo, hi = pts.min(axis=0), pts.max(axis=0)
                center = [rng.uniform(-lo[0], W - hi[0]) if hi[0] - lo[0] < W else W / 2 - (lo[0] + hi[0]) / 2,
                          rng.uniform(-lo[1], H - hi[1]) if hi[1] - lo[1] < H else H / 2 - (lo[1] + hi[1]) / 2]
                pts += center
                tag = "far" if label == "too_far" else ("hard" if hard else "normal")
                w.writerow([label, f"demo_{tag}", W, H] + [round(v, 5) for p in pts for v in (p[0] / W, p[1] / H)])
    print(f"已產生 {len(labels) * PER_LABEL} 筆練習樣本：{out}")


if __name__ == "__main__":
    main()
