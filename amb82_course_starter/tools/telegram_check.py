"""第 6 節小工具：查 Bot 是否正常、找出自己的 chatID、試傳一則訊息。

用法（Token 只用在這次執行，程式不會存起來）：
  python telegram_check.py                      執行後再貼上 Token
  python telegram_check.py --token 123:ABC      直接指定
  python telegram_check.py --token 123:ABC --say 測試訊息

找 chatID 的步驟：
  1. 手機 Telegram 搜尋自己的 Bot，按「開始」並隨便傳一句話
  2. 執行這支程式，它會列出最近的訊息與對應的 chatID
  3. 把 chatID 填進 06_telegram_bot.ino 的 ALLOWED_CHAT_ID
"""
import argparse
import getpass
import json
import sys
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method, params=None):
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode() if params else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8", "ignore") or '{"ok":false}')
    except Exception as e:
        print("連不上 Telegram：", e)
        print("學校網路可能擋住 api.telegram.org，改用手機熱點試試看")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token")
    parser.add_argument("--say", help="順便傳一則訊息給最後一個聊天對象")
    args = parser.parse_args()
    token = args.token or getpass.getpass("貼上 Bot Token（輸入時不會顯示）：").strip()
    if ":" not in token:
        print("Token 格式看起來不對，應該像 123456789:AAxxxxxxxx")
        return 1

    me = call(token, "getMe")
    if not me:
        return 1
    if not me.get("ok"):
        print("Token 無效：", me.get("description"))
        return 1
    bot = me["result"]
    print(f"Bot 正常：@{bot.get('username')}（{bot.get('first_name')}）")

    updates = call(token, "getUpdates", {"limit": 10})
    msgs = [u for u in (updates or {}).get("result", []) if "message" in u]
    if not msgs:
        print("\n還沒有收到任何訊息。請先在手機上對這個 Bot 說一句話，再重新執行。")
        print("（Bot 只看得到「開始對話之後」的訊息）")
        return 0

    print("\n最近的訊息：")
    last_chat = None
    for u in msgs[-5:]:
        m = u["message"]
        chat = m.get("chat", {})
        last_chat = chat.get("id")
        who = chat.get("username") or chat.get("first_name") or chat.get("title", "")
        print(f"  chatID {chat.get('id')}　{who}：{m.get('text', '（非文字訊息）')}")
    print(f"\n把這個 chatID 填進 06_telegram_bot.ino：{last_chat}")

    if args.say and last_chat:
        r = call(token, "sendMessage", {"chat_id": last_chat, "text": args.say})
        print("傳送結果：", "成功" if r and r.get("ok") else r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
