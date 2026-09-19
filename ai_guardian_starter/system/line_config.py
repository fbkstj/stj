"""
LINE Messaging API 金鑰：只從環境變數讀取，程式裡不存放金鑰。

先在命令提示字元設定（和關卡6 用的是同一個變數）：
    set LINE_TOKEN=你的Channel access token
"""
import os

CHANNEL_ACCESS_TOKEN = (os.environ.get("LINE_TOKEN")
                        or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))
