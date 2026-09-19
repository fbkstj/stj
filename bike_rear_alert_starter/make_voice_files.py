"""產生語音檔：用 Windows 的中文語音把 9 段提示語存成 WAV。

輸出：sd_card/01/001.wav～009.wav
  - 沒接 ESP32 時，電腦直接播放這個資料夾的檔案
  - 接 DFPlayer 時，把整個「01」資料夾複製到 microSD 卡（FAT32）的根目錄

想用自己的聲音：用手機錄好 9 段，轉成 WAV，照同樣的編號命名後放進 sd_card/01/ 即可
（DFPlayer 也支援 MP3，但電腦播放只支援 WAV）。每段盡量在 1.2 秒內說完。

用法：python make_voice_files.py
"""
import array
import os
import time
import wave

import pyttsx3

from voice import CLIPS

HERE = os.path.dirname(os.path.abspath(__file__))
CARD = os.path.join(HERE, "sd_card", "01")


def pick_chinese_voice(engine):
    for v in engine.getProperty("voices"):
        tag = f"{v.id} {v.name}".lower()
        if any(k in tag for k in ("zh-tw", "zh_tw", "hanhan", "yating", "zhiwei", "chinese")):
            engine.setProperty("voice", v.id)
            return v.name
    return None


def trim_silence(path, threshold=500, pad_sec=0.03):
    """剪掉前後的靜音，讓提示更快開始（只處理 16 位元 WAV）。回傳剪完的秒數。"""
    with wave.open(path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
    if params.sampwidth != 2:
        return params.nframes / params.framerate
    samples = array.array("h", frames)
    ch = params.nchannels
    loud = [i for i in range(0, len(samples), ch) if abs(samples[i]) > threshold]
    if not loud:
        return params.nframes / params.framerate
    pad = int(pad_sec * params.framerate) * ch
    start = max(0, loud[0] - pad)
    end = min(len(samples), loud[-1] + ch + pad)
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(samples[start:end].tobytes())
    return (end - start) / ch / params.framerate


def main():
    os.makedirs(CARD, exist_ok=True)
    engine = pyttsx3.init()
    name = pick_chinese_voice(engine)
    if not name:
        print("找不到中文語音：請到 Windows 設定 → 時間與語言 → 語音，新增「中文（台灣）」語音後再執行")
        return
    print("使用語音：", name)
    engine.setProperty("rate", 210)
    for n, text in CLIPS.items():
        engine.save_to_file(text, os.path.join(CARD, f"{n:03d}.wav"))
    engine.runAndWait()

    time.sleep(0.5)
    for n, text in CLIPS.items():
        src = os.path.join(CARD, f"{n:03d}.wav")
        if not os.path.exists(src) or os.path.getsize(src) < 1000:
            print(f"  {n:03d}.wav 產生失敗")
            continue
        sec = trim_silence(src)
        print(f"  {n:03d}.wav  {text}（{sec:.2f} 秒）")
    print("完成。接 DFPlayer 時，把 sd_card 裡的「01」資料夾複製到 microSD 卡（FAT32 格式）的根目錄。")


if __name__ == "__main__":
    main()
