"""語音指令解析：把辨識出來的文字，變成 (動作, 參數)。

解析結果是「意圖」，不管現在是哪個應用程式模式；
同一個意圖在不同模式怎麼執行（例如「靜音」在會議模式是關麥克風），由 actions.py 決定。

這支程式不需要麥克風，可以直接用 test_voice_commands.py 測試。
判斷順序很重要：先比對越特別的句子（例如「關閉程式」「換播」），
再比對一般的句子（例如「播放」），避免「關閉這首換播稻香」被當成「關閉這首」。
"""
import re

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_to_int(s):
    """把「三十」「十五」「兩」這類中文數字轉成整數（0～99）。"""
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        tens, _, ones = s.partition("十")
        return CN_DIGITS.get(tens, 1) * 10 + CN_DIGITS.get(ones, 0)
    return CN_DIGITS.get(s, 0)


NUM = r"(\d+|[零一二兩三四五六七八九十]+)"


def parse_seconds(text, default=10):
    """從「快轉一分半」「倒退 30 秒」「往前兩分鐘」這類句子算出秒數。"""
    total = 0
    m = re.search(NUM + r"\s*(?:個)?(?:分鐘|分)(半)?", text)
    if m:
        total += cn_to_int(m.group(1)) * 60 + (30 if m.group(2) else 0)
    elif "半分鐘" in text:
        total += 30
    m = re.search(NUM + r"\s*秒", text)
    if m:
        total += cn_to_int(m.group(1))
    if total == 0:
        m = re.search(NUM, text)
        if m:
            total = cn_to_int(m.group(1))
    return total if total > 0 else default


def parse_steps(text, default=3):
    m = re.search(NUM + r"\s*(?:格|次|下)", text)
    return max(1, min(20, cn_to_int(m.group(1)))) if m else default


def _has(text, words):
    return any(w in text for w in words)


EXIT = ["關閉程式", "結束程式", "退出程式", "關掉程式", "離開程式"]
LOCK = ["鎖定手勢", "暫停手勢", "關閉手勢", "停用手勢"]
UNLOCK = ["解鎖手勢", "啟用手勢", "開啟手勢", "恢復手勢"]
SWITCH = r"(?:關閉這首|關掉這首)?(?:換播|換聽|換成|換一首|換開啟|換首)\s*(.+)"
REQUEST = r"(?:我想聽|想聽|我要聽|點歌|點播|來一首|播一首|放一首|幫我播放?|播放|搜尋)\s*(.+)"
CLOSE = ["關閉這首", "關掉這首", "關閉影片", "關掉影片", "關閉音樂", "關掉音樂", "關閉分頁", "不要聽了", "別播了", "不要播了"]
OPEN_YT = ["開啟YT", "打開YT", "開YT", "開啟youtube", "打開youtube", "開youtube"]
SKIP = ["跳過廣告", "略過廣告", "跳廣告", "略過"]
FULL = ["全螢幕", "全屏"]
EXIT_FULL = ["離開全螢幕", "退出全螢幕"]
NEXT = ["下一部", "下一首", "下一個影片", "下一支", "換一首", "換一部"]
PREV_VIDEO = ["上一部", "上一首", "上一個影片", "上一支"]
FASTER = ["加速", "播快一點", "快一點播", "速度加快"]
SLOWER = ["減速", "播慢一點", "慢一點播", "速度放慢"]
CAPTIONS = ["字幕"]
VIDEO_MUTE = ["影片靜音", "影片取消靜音"]
SYSTEM_MUTE = ["系統靜音", "電腦靜音"]
MUTE = ["靜音", "取消靜音", "解除靜音"]
VOL_UP = ["大聲", "音量調大", "提高音量", "增加音量", "音量大", "音量放大"]
VOL_DOWN = ["小聲", "音量調小", "降低音量", "減少音量", "音量小", "音量縮小"]
BACK = ["倒退", "後退", "往後", "倒轉", "退回"]
FORWARD = ["快轉", "前進", "往前", "跳過"]
PAUSE = ["暫停", "停一下", "停止播放", "先停"]
PLAY = ["播放", "繼續", "開始播放"]
GENERIC_MEDIA = {"影片", "音樂", "歌", "歌曲", "一下", ""}

# 應用程式模式
AUTO_PROFILE = ["自動切換", "自動模式", "自動偵測"]
PROFILE_SWITCH = r"(?:切換到|切換成|換到|進入|改成|使用|開啟)?(.+?)模式"
PROFILE_ALIASES = {
    "powerpoint": ["簡報", "投影片", "powerpoint", "ppt"],
    "pdf": ["pdf", "文件", "閱讀"],
    "teams": ["teams"],
    "zoom": ["zoom"],
    "meet": ["meet"],
    "meeting": ["會議", "視訊"],
    "youtube": ["youtube", "yt", "影片", "影音"],
}
# 簡報與文件
START_HERE = ["從這頁放映", "從這頁開始", "從目前這頁", "從這張放映"]
START_SHOW = ["開始放映", "放映簡報", "播放簡報", "開始簡報"]
END_SHOW = ["結束放映", "停止放映", "離開放映", "結束簡報"]
BLACK = ["黑畫面", "黑屏", "螢幕變黑", "畫面變黑"]
WHITE = ["白畫面", "白屏", "螢幕變白", "畫面變白"]
LASER = ["雷射筆", "雷射"]
PEN = ["畫筆", "原子筆", "螢光筆"]
ERASE = ["清除筆跡", "擦掉", "清除畫筆", "清掉筆跡"]
ARROW = ["箭頭", "游標", "滑鼠指標"]
LAST_PAGE = ["最後一頁", "最後一張", "最後頁"]
NEXT_PAGE = ["下頁", "翻頁", "下一頁", "下一張", "後一頁", "後一張"]
PREV_PAGE = ["上頁", "翻回去", "上一頁", "上一張", "前一頁", "前一張"]
ZOOM_IN = ["放大", "拉近"]
ZOOM_OUT = ["縮小", "拉遠"]
FIT_PAGE = ["整頁", "符合頁面", "原始大小", "恢復大小"]
# 視訊會議
MIC = ["麥克風"]
CAMERA = ["鏡頭", "攝影機"]
RAISE = ["舉手", "放下手"]


def _clean_query(q):
    q = re.sub(r"(?:的歌|的歌曲|的mv|mv|歌曲|音樂|影片)$", "", q.strip(), flags=re.IGNORECASE).strip()
    return None if q in GENERIC_MEDIA else q


def parse(text, wake_word=""):
    """回傳 dict(action=..., arg=...) 或 None（聽不懂或沒有喚醒詞）。"""
    t = re.sub(r"[\s，。！？、,.!?]", "", text or "")
    if wake_word:
        if not t.startswith(wake_word):
            return None
        t = t[len(wake_word):]
    tl = t.lower()
    if not t:
        return None

    if _has(t, EXIT):
        return {"action": "exit", "arg": None}
    if _has(t, LOCK):
        return {"action": "lock", "arg": None}
    if _has(t, UNLOCK):
        return {"action": "unlock", "arg": None}
    if _has(t, AUTO_PROFILE):
        return {"action": "auto_profile", "arg": None}
    m = re.search(PROFILE_SWITCH, tl)
    if m:
        for name, words in PROFILE_ALIASES.items():
            if _has(m.group(1), words):
                return {"action": "switch_profile", "arg": name}

    # 簡報、文件
    if _has(t, START_HERE):
        return {"action": "start_here", "arg": None}
    if _has(t, START_SHOW):
        return {"action": "start_show", "arg": None}
    if _has(t, END_SHOW):
        return {"action": "end_show", "arg": None}
    if _has(t, BLACK):
        return {"action": "black_screen", "arg": None}
    if _has(t, WHITE):
        return {"action": "white_screen", "arg": None}
    if _has(t, LASER):
        return {"action": "laser", "arg": None}
    if _has(t, PEN):
        return {"action": "pen", "arg": None}
    if _has(t, ERASE):
        return {"action": "erase_ink", "arg": None}
    if _has(t, ARROW):
        return {"action": "arrow_pointer", "arg": None}
    m = re.search(r"第" + NUM + r"(?:頁|張)", t)
    if m and cn_to_int(m.group(1)) > 0:
        return {"action": "goto_page", "arg": cn_to_int(m.group(1))}
    if _has(t, LAST_PAGE):
        return {"action": "last_page", "arg": None}
    if _has(t, NEXT_PAGE):
        return {"action": "next_page", "arg": None}
    if _has(t, PREV_PAGE):
        return {"action": "prev_page", "arg": None}
    m = re.match(r"(?:跳到|跳去|切到)(.+?)(?:那一?頁|那一?張|的投影片|投影片)?$", t)
    if m and not re.search(r"\d|秒|分鐘|廣告", m.group(1)):
        return {"action": "goto_title", "arg": m.group(1)}
    if _has(t, FIT_PAGE):
        return {"action": "fit_page", "arg": None}

    # 視訊會議
    if _has(t, MIC):
        return {"action": "mic_toggle", "arg": None}
    if _has(t, CAMERA):
        return {"action": "camera_toggle", "arg": None}
    if _has(t, RAISE):
        return {"action": "raise_hand", "arg": None}

    m = re.search(SWITCH, t)
    if m and _clean_query(m.group(1)):
        return {"action": "play_song", "arg": {"query": _clean_query(m.group(1)), "close_current": True}}
    if _has(t, CLOSE):
        return {"action": "close_video", "arg": None}
    if _has(tl, [w.lower() for w in OPEN_YT]):
        return {"action": "open_youtube", "arg": None}
    if _has(t, SKIP) and "秒" not in t:
        return {"action": "skip_ad", "arg": None}
    if _has(t, EXIT_FULL):
        return {"action": "fullscreen", "arg": None}
    if _has(t, FULL):
        return {"action": "fullscreen", "arg": None}
    if _has(t, NEXT):
        return {"action": "next_video", "arg": None}
    if _has(t, PREV_VIDEO):
        return {"action": "prev_video", "arg": None}
    if _has(t, FASTER):
        return {"action": "speed_up", "arg": None}
    if _has(t, SLOWER):
        return {"action": "speed_down", "arg": None}
    if _has(t, CAPTIONS):
        return {"action": "captions", "arg": None}
    if _has(t, SYSTEM_MUTE):
        return {"action": "system_mute", "arg": None}
    if _has(t, VIDEO_MUTE):
        return {"action": "video_mute", "arg": None}
    if _has(t, MUTE):
        return {"action": "mute", "arg": None}
    if _has(t, VOL_UP):
        return {"action": "volume_up", "arg": parse_steps(t)}
    if _has(t, VOL_DOWN):
        return {"action": "volume_down", "arg": parse_steps(t)}
    if _has(t, ZOOM_IN):
        return {"action": "zoom_in", "arg": None}
    if _has(t, ZOOM_OUT):
        return {"action": "zoom_out", "arg": None}
    if _has(t, BACK):
        return {"action": "seek_back", "arg": parse_seconds(t)}
    if _has(t, FORWARD):
        return {"action": "seek_forward", "arg": parse_seconds(t)}
    if _has(t, PAUSE):
        return {"action": "play_pause", "arg": None}

    m = re.match(REQUEST, t)
    if m and _clean_query(m.group(1)):
        return {"action": "play_song", "arg": {"query": _clean_query(m.group(1)), "close_current": False}}
    if _has(t, PLAY):
        return {"action": "play_pause", "arg": None}
    return None
