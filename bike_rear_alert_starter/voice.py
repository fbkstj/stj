"""車種語音提示：決定「什麼時候、說哪一段」，並送到 ESP32（DFPlayer）或電腦喇叭播放。

語音檔放在 sd_card/01/（電腦播放與 microSD 卡共用同一份），編號如下：
  001 後方機車        002 後方汽車        003 後方大型車
  004 後方多台車      005 危險，注意      006 警示系統啟動
  007 危險，機車      008 危險，汽車      009 危險，大型車

說話規則：
  1. 一台車第一次進入「注意」或「危險」時，說出車種；同一台車只說一次
  2. 同時有兩台以上新的車 → 說「後方多台車」；其中有公車或貨車 → 優先說「後方大型車」
  3. 每一次警示期間第一次升到「危險」→ 立刻說「危險，＋車種」（會打斷正在播放的語音，
     所以危險語音本身也帶車種）；危險的車有兩種以上時說「危險，注意」
  4. 兩段語音至少間隔 cooldown 秒，避免講不完；來不及說的車，等間隔到了再說
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CLIPS = {
    1: "後方機車",
    2: "後方汽車",
    3: "後方大型車",
    4: "後方多台車",
    5: "危險，注意",
    6: "警示系統啟動",
    7: "危險，機車",
    8: "危險，汽車",
    9: "危險，大型車",
}
CLIP_MOTORCYCLE, CLIP_CAR, CLIP_BIG, CLIP_MULTI, CLIP_DANGER, CLIP_READY = 1, 2, 3, 4, 5, 6
CLIP_DANGER_MOTORCYCLE, CLIP_DANGER_CAR, CLIP_DANGER_BIG = 7, 8, 9

# 傳給 ESP32 顯示用的車種代碼
VEHICLE_CODE = {"motorcycle": "M", "car": "C", "bus": "B", "truck": "B"}


def vehicle_group(name, big_classes=("bus", "truck")):
    """語音與成績用的車種分組：公車、貨車都算「大型車」。"""
    if name in big_classes:
        return "big"
    return name


class Announcer:
    def __init__(self, cooldown=1.5, big_classes=("bus", "truck")):
        self.cooldown = cooldown
        self.big = set(big_classes)
        self.announced = set()
        self.last_play = -1e9
        self.danger_said = False

    def _group(self, name):
        return "big" if name in self.big else ("motorcycle" if name == "motorcycle" else "car")

    def update(self, now, alerting, level, event):
        """alerting：目前正在警示的車 [(編號, 車種, 等級), ...]
        level：整體警示等級；event：AlertState 這次回傳的事件。
        回傳 (語音編號, 說明文字)，不需要說話時回傳 None。"""
        if event == "alert_off":
            self.danger_said = False
            return None

        new = [(tid, name) for tid, name, lv in alerting if tid not in self.announced]

        if level == 2 and not self.danger_said:
            self.danger_said = True
            self.announced.update(tid for tid, _ in new)
            self.last_play = now
            groups = {self._group(name) for _, name, lv in alerting if lv == 2}
            clip = CLIP_DANGER
            if len(groups) == 1:
                clip = {"motorcycle": CLIP_DANGER_MOTORCYCLE, "car": CLIP_DANGER_CAR,
                        "big": CLIP_DANGER_BIG}[groups.pop()]
            return clip, CLIPS[clip]

        if not new or now - self.last_play < self.cooldown:
            return None
        self.announced.update(tid for tid, _ in new)
        self.last_play = now
        names = [name for _, name in new]
        if any(n in self.big for n in names):
            clip = CLIP_BIG
        elif len(names) >= 2:
            clip = CLIP_MULTI
        elif names[0] == "motorcycle":
            clip = CLIP_MOTORCYCLE
        else:
            clip = CLIP_CAR
        return clip, CLIPS[clip]


class PcPlayer:
    """沒有 ESP32 時，用電腦播放 sd_card/01/001.wav～009.wav；找不到音檔就改用嗶聲。"""

    def __init__(self, enabled, folder=os.path.join("sd_card", "01")):
        self.enabled = enabled and os.name == "nt"
        self.folder = folder if os.path.isabs(folder) else os.path.join(HERE, folder)
        if self.enabled and not os.path.exists(os.path.join(self.folder, "001.wav")):
            print("找不到語音檔（sd_card/01/001.wav），請先執行 6_make_voice_files.bat；目前改用嗶聲")

    def play(self, clip):
        if not self.enabled:
            return
        import winsound
        path = os.path.join(self.folder, f"{clip:03d}.wav")
        if os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.Beep(1500 if clip == CLIP_DANGER else 900, 150)


def status_line(level, vehicle_name, ttc):
    """傳給 ESP32 的狀態：S＋等級＋車種代碼＋到達時間（0.1 秒為單位，最多 99）。
    例：S1B25＝注意、大型車、約 2.5 秒；S0N00＝安全。每行不超過 8 個字元。"""
    code = VEHICLE_CODE.get(vehicle_name, "N") if level > 0 else "N"
    tenths = 0 if ttc is None or level == 0 else max(0, min(99, int(round(ttc * 10))))
    return f"S{level}{code}{tenths:02d}"


if __name__ == "__main__":
    # 簡單示範：兩台車先後逼近
    a = Announcer(cooldown=1.5)
    print(a.update(0.0, [(1, "motorcycle", 1)], 1, "alert_on"))
    print(a.update(0.5, [(1, "motorcycle", 1), (2, "truck", 1)], 1, None))
    print(a.update(1.6, [(1, "motorcycle", 1), (2, "truck", 1)], 1, None))
    print(a.update(2.0, [(2, "truck", 2)], 2, "escalate"))
    print(status_line(1, "truck", 2.46))
