"""動作執行：依照目前的「應用程式模式」，把動作變成按鍵、開網頁、點擊或 PowerPoint 指令。

每個模式寫在 config.json 的 profiles：
  window     視窗標題含有這些字，就是這個應用程式
  keys       動作 → 快捷鍵（例如 "next_page": ["right"]）
  voice_map  把語音意圖換成這個模式的動作（例如會議模式的「靜音」＝關麥克風）
  seek       true＝支援 YouTube 的快轉倒退
  skip_ad    true＝支援按下「略過」
  goto       "powerpoint"＝可以用程式介面跳頁、找標題
  gestures   這個模式的手勢對應

不管哪個模式都能用的「共通動作」：音量、系統靜音、開 YouTube、點歌、手勢鎖、切換模式、結束程式。
模擬模式（dry_run）只回傳「會做什麼」，不會真的按鍵。
"""
import glob
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

import cv2
import numpy as np

import ppt_com

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    import win32api
    import win32con
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

ACTION_TEXT = {
    # YouTube
    "play_pause": "播放／暫停", "seek_forward": "快轉", "seek_back": "倒退",
    "video_mute": "影片靜音切換", "fullscreen": "全螢幕切換", "captions": "字幕切換",
    "next_video": "下一部影片", "prev_video": "上一部影片", "speed_up": "播放加速", "speed_down": "播放減速",
    "skip_ad": "按下「略過」", "close_video": "關閉目前影片分頁",
    # 簡報與文件
    "next_page": "下一頁", "prev_page": "上一頁", "first_page": "第一頁", "last_page": "最後一頁",
    "goto_page": "跳頁", "goto_title": "跳到指定投影片", "black_screen": "黑畫面切換", "white_screen": "白畫面切換",
    "start_show": "從頭放映", "start_here": "從這頁放映", "end_show": "結束放映", "laser": "雷射筆",
    "pen": "畫筆", "arrow_pointer": "一般游標", "erase_ink": "清除筆跡",
    "zoom_in": "放大", "zoom_out": "縮小", "fit_page": "恢復頁面大小",
    # 視訊會議
    "mic_toggle": "麥克風開關", "camera_toggle": "鏡頭開關", "raise_hand": "舉手／放下",
    # 共通
    "volume_up": "音量調大", "volume_down": "音量調小", "mute": "系統靜音切換", "system_mute": "系統靜音切換",
    "open_youtube": "開啟 YouTube", "play_song": "搜尋並播放",
    "lock": "手勢已鎖定", "unlock": "手勢已解鎖", "switch_profile": "切換模式", "auto_profile": "自動切換模式",
    "exit": "結束程式",
}
GLOBAL_ACTIONS = {"volume_up", "volume_down", "mute", "system_mute", "open_youtube", "play_song",
                  "lock", "unlock", "switch_profile", "auto_profile", "exit"}
INTERNAL_ACTIONS = {"lock", "unlock", "switch_profile", "auto_profile", "exit"}
SEEK_ACTIONS = {"seek_forward", "seek_back"}
GOTO_ACTIONS = {"goto_page", "goto_title"}
BEEP = {"lock": (400, 150), "unlock": (900, 150), "exit": (300, 250), "switch_profile": (700, 120)}


def imread_unicode(path):
    """cv2.imread 讀不到中文路徑，改用 numpy 讀檔再解碼。"""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE) if data.size else None


def first_video_url(query, timeout=5):
    """查 YouTube 搜尋結果頁，取第一部影片的網址；失敗就回傳搜尋結果頁。"""
    q = urllib.parse.quote(query)
    results = f"https://www.youtube.com/results?search_query={q}"
    try:
        req = urllib.request.Request(results, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-TW"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "ignore")
        m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}", True
    except Exception as e:
        print("搜尋影片失敗，改開搜尋結果頁：", e)
    return results, False


def seek_keys(seconds):
    """把秒數拆成 l（10 秒）與 →（5 秒）的按鍵次數；不足 5 秒的部分四捨五入。"""
    tens, rest = divmod(int(seconds), 10)
    fives = int(round(rest / 5))
    if fives == 2:
        tens, fives = tens + 1, 0
    if tens == 0 and fives == 0:
        fives = 1
    return tens, fives


def window_title(hwnd):
    try:
        return win32gui.GetWindowText(hwnd) if HAS_WIN32 and hwnd else ""
    except Exception:
        return ""


def match_profile(profiles, title):
    """依視窗標題找出模式名稱（照 config.json 的順序比對），找不到回傳 None。"""
    t = title.lower()
    if not t or "airtouch" in t:
        return None
    for name, p in profiles.items():
        if any(k.lower() in t for k in p["window"]):
            return name
    return None


class Actions:
    def __init__(self, cfg, dry_run=False):
        self.cfg = cfg
        self.profiles = cfg["profiles"]
        self.dry_run = dry_run
        self.templates = []
        for p in sorted(glob.glob(os.path.join(HERE, "templates", "*.png"))):
            img = imread_unicode(p)
            if img is not None:
                self.templates.append((os.path.basename(p), img))
        self.gui = None
        if not dry_run:
            import pyautogui
            pyautogui.PAUSE = 0.02
            self.gui = pyautogui

    # ---------- 視窗 ----------
    def find_window(self, profile_name):
        """找這個模式的視窗；目前的前景視窗符合的話優先用它。"""
        if not HAS_WIN32:
            return None
        fg = win32gui.GetForegroundWindow()
        if match_profile({profile_name: self.profiles[profile_name]}, window_title(fg)):
            return fg
        found = []

        def cb(h, _):
            if win32gui.IsWindowVisible(h) and match_profile({profile_name: self.profiles[profile_name]},
                                                             window_title(h)):
                found.append(h)
        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    def focus(self, hwnd):
        """把視窗叫到最前面。Windows 不允許背景程式搶焦點，所以先把輸入佇列接到目前的前景視窗上。"""
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            fg = win32gui.GetForegroundWindow()
            if fg == hwnd:
                return True
            me = win32api.GetCurrentThreadId()
            other = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
            attached = False
            if other and other != me:
                try:
                    win32process.AttachThreadInput(me, other, True)
                    attached = True
                except Exception:
                    pass
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    win32process.AttachThreadInput(me, other, False)
            time.sleep(0.08)
            return win32gui.GetForegroundWindow() == hwnd
        except Exception as e:
            print("切換視窗失敗：", e)
            return False

    def meeting_profile(self):
        """「會議模式」：看哪一個會議軟體的視窗有開，就用那一個。"""
        names = self.cfg["meeting_profiles"]
        if not self.dry_run:
            for name in names:
                if self.find_window(name):
                    return name
        return names[0]

    # ---------- 判斷 ----------
    def resolve(self, action, profile_name):
        """把意圖換成這個模式的實際動作，並判斷是否支援。回傳 (動作, 是否支援)。"""
        profile = self.profiles[profile_name]
        action = profile.get("voice_map", {}).get(action, action)
        if action == "system_mute":
            action = "mute"
        if action in GLOBAL_ACTIONS or action in profile["keys"]:
            return action, True
        if action in SEEK_ACTIONS:
            return action, bool(profile.get("seek"))
        if action == "skip_ad":
            return action, bool(profile.get("skip_ad"))
        if action in GOTO_ACTIONS:
            return action, profile.get("goto") == "powerpoint"
        return action, False

    def describe(self, action, arg):
        label = ACTION_TEXT.get(action, action)
        if action in SEEK_ACTIONS:
            return f"{label} {arg or 10} 秒"
        if action in ("volume_up", "volume_down"):
            return f"{label} {arg or 1} 格"
        if action == "play_song" and arg:
            return f"{'換播' if arg.get('close_current') else '播放'}「{arg['query']}」"
        if action == "goto_page":
            return f"跳到第 {arg} 頁"
        if action == "goto_title":
            return f"跳到「{arg}」那頁"
        if action == "switch_profile":
            return f"切換到「{self.profiles[arg]['name']}」模式" if arg in self.profiles else label
        return label

    # ---------- 執行 ----------
    def beep(self, action):
        if not self.cfg.get("beep", True) or os.name != "nt":
            return
        freq, ms = BEEP.get(action, (1000, 60))
        import winsound
        threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()

    def run(self, action, arg, profile_name):
        """執行動作，回傳 (是否成功, 顯示文字, 實際動作)。"""
        profile = self.profiles[profile_name]
        action, supported = self.resolve(action, profile_name)
        detail = self.describe(action, arg)
        if not supported:
            return False, f"「{profile['name']}」模式沒有「{ACTION_TEXT.get(action, action)}」", action
        if action in INTERNAL_ACTIONS:
            self.beep(action)
            return True, detail, action
        if self.dry_run:
            return True, f"[模擬・{profile['name']}] {detail}", action

        hwnd = None
        if action not in GLOBAL_ACTIONS:
            hwnd = self.find_window(profile_name)
            if not hwnd:
                return False, f"找不到「{profile['name']}」的視窗", action
            if action not in GOTO_ACTIONS and not self.focus(hwnd):
                return False, f"無法切換到「{profile['name']}」視窗", action
        try:
            ok, msg = self._do(action, arg, profile, hwnd)
        except Exception as e:           # pyautogui 的安全機制：滑鼠移到螢幕角落會中止
            return False, f"{ACTION_TEXT.get(action, action)}失敗：{e}", action
        if ok:
            self.beep(action)
        return ok, msg or detail, action

    def _do(self, action, arg, profile, hwnd):
        g = self.gui
        if action in profile["keys"]:
            g.hotkey(*profile["keys"][action])
            return True, None
        if action in SEEK_ACTIONS:
            tens, fives = seek_keys(arg or 10)
            fwd = action == "seek_forward"
            g.press("l" if fwd else "j", presses=tens, interval=0.05)
            g.press("right" if fwd else "left", presses=fives, interval=0.05)
            return True, None
        if action in ("volume_up", "volume_down"):
            g.press("volumeup" if action == "volume_up" else "volumedown", presses=arg or 1, interval=0.03)
            return True, None
        if action == "mute":
            g.press("volumemute")
            return True, None
        if action == "open_youtube":
            webbrowser.open(self.cfg["youtube_home"])
            return True, None
        if action == "play_song":
            if arg.get("close_current"):
                old = self.find_window("youtube")
                if old and self.focus(old):
                    g.hotkey("ctrl", "w")
                    time.sleep(0.3)
            url, direct = first_video_url(arg["query"])
            webbrowser.open(url)
            return True, self.describe(action, arg) + ("" if direct else "（開啟搜尋結果）")
        if action == "goto_page":
            ok, msg = ppt_com.goto(int(arg))
            if ok is None:                # 沒有程式介面：放映中輸入頁碼再按 Enter 也能跳頁
                if not self.focus(hwnd):
                    return False, msg
                g.write(str(int(arg)), interval=0.05)
                g.press("enter")
                return True, f"跳到第 {arg} 頁（按鍵）"
            return ok, msg
        if action == "goto_title":
            return ppt_com.goto_title(arg)
        if action == "skip_ad":
            return self.click_skip(hwnd)
        return False, f"不認得的動作：{action}"

    def click_skip(self, hwnd):
        """在 YouTube 視窗裡找「略過」按鈕，找到才點，點完滑鼠移回原位。"""
        if not self.templates:
            return False, "templates 資料夾沒有按鈕圖片，請先執行 make_skip_template.py"
        from PIL import ImageGrab
        x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
        shot = cv2.cvtColor(np.array(ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)), cv2.COLOR_RGB2GRAY)
        best = (0.0, None, None)
        for name, tpl in self.templates:
            for scale in np.linspace(0.6, 1.6, 11):
                t = cv2.resize(tpl, None, fx=scale, fy=scale)
                if t.shape[0] > shot.shape[0] or t.shape[1] > shot.shape[1]:
                    continue
                _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(shot, t, cv2.TM_CCOEFF_NORMED))
                if score > best[0]:
                    best = (score, (loc[0] + t.shape[1] // 2, loc[1] + t.shape[0] // 2), name)
        score, center, name = best
        if score < self.cfg["skip_match_threshold"]:
            return False, f"畫面上沒有「略過」按鈕（相似度 {score:.2f}）"
        old = self.gui.position()
        self.gui.click(x1 + center[0], y1 + center[1])
        self.gui.moveTo(*old)
        return True, f"已按下「略過」（{name}，相似度 {score:.2f}）"
