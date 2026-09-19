"""關卡6:用 LINE Messaging API 發通報訊息(廣播給官方帳號的所有好友)。

先設定金鑰(不要把金鑰寫進程式、也不要上傳到網路):
    set LINE_TOKEN=你的Channel access token
再執行:
    python step6_line.py

用 Python 內建的 http.client 發送(不用 requests 套件),
部分學校電腦的防毒軟體會讓 requests 卡住不動。
"""
import http.client
import json
import os
import ssl


def send_line(text):
    token = os.environ.get("LINE_TOKEN")
    if not token:
        print("找不到 LINE_TOKEN,請先執行:set LINE_TOKEN=你的金鑰")
        return False
    body = json.dumps({"messages": [{"type": "text", "text": text}]})
    conn = http.client.HTTPSConnection("api.line.me", timeout=8,
                                       context=ssl.create_default_context())
    try:
        conn.request("POST", "/v2/bot/message/broadcast", body=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        })
        resp = conn.getresponse()
        detail = resp.read().decode("utf-8", errors="replace")
        print("狀態碼", resp.status, detail)
        return resp.status == 200
    except OSError as e:
        print("連線失敗:", e)
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    send_line("【測試】AI 監控通報系統:收到這則訊息代表 LINE 串接成功")
