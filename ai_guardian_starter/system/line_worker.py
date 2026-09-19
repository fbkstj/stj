"""
獨立的 LINE 推播工作程式，一次執行只做一件事：送出一則廣播訊息就結束。

用法：python line_worker.py "訊息內容"

用 Python 內建的 http.client，不用 requests 套件：
有些電腦的防毒軟體（SSL 深度檢測）會讓 requests 卡住、不理會 timeout，http.client 則正常。

每次推播開一個獨立行程（不是背景執行緒）：就算網路卡住，
也只卡住這個行程，不會拖累監控畫面或其他次推播。
"""
import http.client
import json
import ssl
import sys
import time

from line_config import CHANNEL_ACCESS_TOKEN

API_HOST = "api.line.me"
API_PATH = "/v2/bot/message/broadcast"
MAX_RETRIES = 3
TIMEOUT_SEC = 8


def post_broadcast(message):
    if not CHANNEL_ACCESS_TOKEN:
        print("[LINE] 找不到金鑰，請先執行：set LINE_TOKEN=你的金鑰", flush=True)
        return
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
    }
    body = json.dumps({"messages": [{"type": "text", "text": message}]})

    for attempt in range(1, MAX_RETRIES + 1):
        conn = None
        try:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(API_HOST, timeout=TIMEOUT_SEC, context=ctx)
            conn.request("POST", API_PATH, body=body, headers=headers)
            resp = conn.getresponse()
            status = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
            if status == 200:
                print(f"[LINE] 推播成功(第{attempt}次嘗試):{message}", flush=True)
                return
            print(f"[LINE] 推播失敗 status={status} body={resp_body}", flush=True)
            return
        except OSError as e:
            print(f"[LINE] 第{attempt}次嘗試發生連線例外:{type(e).__name__}: {e}", flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)
        finally:
            if conn is not None:
                conn.close()

    print(f"[LINE] 重試 {MAX_RETRIES} 次仍失敗,放棄推播:{message}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:python line_worker.py \"訊息內容\"", flush=True)
        sys.exit(1)
    post_broadcast(sys.argv[1])
