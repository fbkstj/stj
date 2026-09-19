"""語音輸入：在背景錄音，偵測到有人說話就送去辨識，再把文字交給 voice_commands.parse。

- 麥克風模式：sounddevice 錄音 → 音量判斷一句話的開始與結束 → Google 語音辨識（需要網路）
- 打字模式（--text）：在命令提示字元打字代替說話，沒有麥克風也能測試

音量判斷：先安靜 1 秒量背景雜音，音量超過「雜音 × voice_threshold_ratio」就當作開始說話，
安靜超過 voice_end_silence_sec 秒就當作說完。
"""
import queue
import threading
import time

import numpy as np

import voice_commands


class VoiceListener:
    def __init__(self, cfg, on_command, on_status, text_mode=False):
        self.cfg = cfg
        self.on_command = on_command      # on_command(文字, 解析結果, 辨識花費秒數)
        self.on_status = on_status        # on_status(狀態文字)
        self.text_mode = text_mode
        self.running = False
        self.enabled = True

    def start(self):
        self.running = True
        target = self._text_loop if self.text_mode else self._mic_loop
        threading.Thread(target=target, daemon=True).start()

    def stop(self):
        self.running = False

    def _handle(self, text, cost):
        cmd = voice_commands.parse(text, self.cfg.get("voice_wake_word", ""))
        self.on_command(text, cmd, cost)

    # ---------- 打字模式 ----------
    def _text_loop(self):
        self.on_status("打字模式：在命令提示字元輸入指令後按 Enter")
        while self.running:
            try:
                text = input("語音指令> ").strip()
            except EOFError:
                return
            if text and self.enabled:
                self._handle(text, 0.0)

    # ---------- 麥克風模式 ----------
    def _mic_loop(self):
        try:
            import sounddevice as sd
            import speech_recognition as sr
        except ImportError as e:
            self.on_status(f"語音功能無法使用（{e.name} 沒有安裝）")
            return
        rate = 16000
        block = int(rate * 0.05)                 # 每 0.05 秒一塊
        blocks = queue.Queue()

        def callback(indata, frames, time_info, status):
            blocks.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block, callback=callback)
            stream.start()
        except Exception as e:
            self.on_status(f"打不開麥克風：{e}")
            return

        self.on_status("語音校正中，請安靜 1 秒…")
        noise = []
        end = time.time() + 1.0
        while time.time() < end:
            noise.append(float(np.sqrt(np.mean(blocks.get().astype(np.float32) ** 2))))
        floor = max(np.median(noise), 50.0)
        threshold = max(floor * self.cfg["voice_threshold_ratio"], self.cfg["voice_min_rms"])
        self.on_status(f"語音待命中（門檻 {threshold:.0f}）")
        recognizer = sr.Recognizer()

        speech, silent, talking = [], 0.0, False
        pre = []                                  # 保留開始說話前 0.3 秒，避免第一個字被切掉
        while self.running:
            try:
                chunk = blocks.get(timeout=0.5)
            except queue.Empty:
                continue
            if not self.enabled:
                speech, talking = [], False
                continue
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if not talking:
                pre = (pre + [chunk])[-6:]
                if rms > threshold:
                    talking, speech, silent = True, list(pre), 0.0
                continue
            speech.append(chunk)
            silent = silent + 0.05 if rms < threshold else 0.0
            length = len(speech) * 0.05
            if silent >= self.cfg["voice_end_silence_sec"] or length >= self.cfg["voice_max_sec"]:
                talking = False
                if length - silent < 0.3:          # 太短，多半是雜音
                    continue
                audio = sr.AudioData(np.concatenate(speech).tobytes(), rate, 2)
                self.on_status("辨識中…")
                t0 = time.time()
                try:
                    text = recognizer.recognize_google(audio, language=self.cfg["voice_language"])
                except sr.UnknownValueError:
                    self.on_status("沒聽清楚，請再說一次")
                    continue
                except sr.RequestError as e:
                    self.on_status(f"語音辨識連線失敗：{e}")
                    continue
                self._handle(text, time.time() - t0)
                self.on_status("語音待命中")
        stream.stop()
        stream.close()
