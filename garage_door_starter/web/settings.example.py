# -*- coding: utf-8 -*-
"""設定範本：複製成 settings.py 再填入自己的設定，不要把填好的檔案公開。"""

# ---------- 網頁 ----------
HTTP_PORT = 8000
LOGIN_PASSWORD = "自己設一組密碼"      # 進入控制台要輸入的密碼；設成 "" 就不用登入

# ---------- 攝影機（地下室那台 Tapo）----------
# stream1 = 高畫質、stream2 = 省效能。網頁看門開了沒，stream2 就夠。
CAMERA_RTSP = "rtsp://攝影機帳號:攝影機密碼@攝影機IP:554/stream2"

# ---------- MQTT（與 ESP32 韌體的 secrets.h 一致）----------
MQTT_HOST = "你的broker網址"
MQTT_PORT = 8883                # TLS
MQTT_USER = "你的MQTT帳號"
MQTT_PASS = "你的MQTT密碼"

TOPIC_OPEN = "自己取一段別人猜不到的前綴/open"
TOPIC_PAUSE = "自己取一段別人猜不到的前綴/pause"
TOPIC_CLOSE = "自己取一段別人猜不到的前綴/close"
TOPIC_STATE = "自己取一段別人猜不到的前綴/state"
TOPIC_AVAIL = "自己取一段別人猜不到的前綴/avail"
TOPIC_LOG = "自己取一段別人猜不到的前綴/log"
