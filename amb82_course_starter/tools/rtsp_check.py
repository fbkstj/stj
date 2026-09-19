"""第 2 節小工具：檢查 RTSP 串流連不連得上、抓一張畫面存檔。

VLC 打不開時，先用這支程式判斷是「板子沒串流」還是「VLC 設定問題」。
需要電腦有 ffmpeg（ffprobe、ffmpeg 兩個指令）；沒有的話會提示怎麼裝。

用法：
  python rtsp_check.py rtsp://192.168.1.50:554
  python rtsp_check.py rtsp://192.168.1.50:554 --tcp      改用 TCP 傳輸（畫面破格時試這個）
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def need(tool):
    if shutil.which(tool):
        return True
    print(f"找不到 {tool}。請安裝 ffmpeg 後重試：")
    print("  Windows：winget install Gyan.FFmpeg　或到 https://ffmpeg.org 下載後把 bin 加入 PATH")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="例如 rtsp://192.168.1.50:554")
    parser.add_argument("--tcp", action="store_true", help="用 TCP 傳輸（預設 UDP）")
    parser.add_argument("--seconds", type=int, default=5, help="測試幾秒（預設 5）")
    args = parser.parse_args()
    if not (need("ffprobe") and need("ffmpeg")):
        return 1

    transport = ["-rtsp_transport", "tcp" if args.tcp else "udp"]
    print(f"測試 {args.url}（{'TCP' if args.tcp else 'UDP'}）…")

    t0 = time.time()
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", *transport, "-select_streams", "v:0",
                                "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
                                "-of", "default=noprint_wrappers=1", args.url],
                               capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        print("等了 30 秒沒有回應：網址或網路不通（板子沒串流、不同網段、被防火牆擋住）")
        return 1
    if probe.returncode != 0:
        print("連不上或沒有影像。常見原因：")
        print("  1. 板子沒在串流（序列埠看不到 rtsp:// 網址）")
        print("  2. 電腦和板子不在同一個網段（學校 WiFi 常隔離裝置）")
        print("  3. 防火牆擋住；換手機熱點或用板子的 AP 模式測試")
        print("ffprobe 訊息：", probe.stderr.strip()[:300])
        return 1
    print(f"連上了（花了 {time.time() - t0:.1f} 秒）")
    for line in probe.stdout.strip().splitlines():
        print("  ", line)

    out = os.path.join(HERE, "rtsp_snapshot.jpg")
    try:
        grab = subprocess.run(["ffmpeg", "-y", "-v", "error", *transport, "-i", args.url,
                               "-frames:v", "1", out], capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        print("抓畫面逾時，串流可能中斷了")
        return 1
    if grab.returncode == 0 and os.path.exists(out):
        print(f"已存下一張畫面：{out}（{os.path.getsize(out) // 1024} KB）")
    else:
        print("抓畫面失敗：", grab.stderr.strip()[:300])

    print(f"\n接著量 {args.seconds} 秒內收到幾張畫面…")
    try:
        count = subprocess.run(["ffmpeg", "-v", "error", "-stats", *transport, "-t", str(args.seconds),
                                "-i", args.url, "-f", "null", "-"], capture_output=True, text=True,
                               timeout=args.seconds + 30)
    except subprocess.TimeoutExpired:
        print("統計逾時，串流可能中斷了")
        return 1
    tail = (count.stderr or "").strip().splitlines()
    print(tail[-1][:200] if tail else "（沒有統計資訊）")
    print("\n提示：frame= 的數字除以秒數就是實際張數；比設定的 FPS 低很多，代表網路塞住，把位元率調小。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
