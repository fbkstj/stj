"""
把訊息廣播（broadcast）給 LINE 官方帳號的所有好友。

用「廣播」而不是「推播給指定使用者」，是因為廣播不需要知道對方的 User ID，
設定簡單很多；代價是官方帳號的每個好友都會收到。

實際發送交給獨立的 line_worker.py 子行程：網路卡住時不會卡住監控畫面。
"""
import subprocess
import sys
from pathlib import Path

WORKER_SCRIPT = Path(__file__).parent / "line_worker.py"


def send_line_alert(message):
    """非阻塞:立刻回傳,實際送出動作交給獨立子行程處理,不會卡住攝影機畫面。"""
    print(f"[LINE] 啟動獨立行程推播:{message}", flush=True)
    subprocess.Popen([sys.executable, str(WORKER_SCRIPT), message])


if __name__ == "__main__":
    # 直接執行這個檔案可以單獨測試推播有沒有成功(不用開攝影機)
    print("送出測試訊息...")
    from line_worker import post_broadcast
    post_broadcast("公共場所AI監控通報:LINE 推播測試訊息,收到代表串接成功。")
    print("已送出,請檢查手機 LINE。")
