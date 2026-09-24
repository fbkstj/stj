# 鐵捲門 ESP32 × MQTT 遠端控制 · 程式包

用 ESP32 加一片四路繼電器模組，把舊式鐵捲門主板的「開／停／關」三個按鍵接出來，
手機 App 或網頁按一下就等於按了牆上的按鈕。

搭配實作紀錄一起看：<https://fbkstj.github.io/stj/#page/garage_door_mqtt_project>

## 檔案

```
firmware/garage_door_mqtt/
    garage_door_mqtt.ino     ESP32 韌體（Arduino）
    secrets.h.example        設定範本 → 複製成 secrets.h 再填自己的
web/
    door_web.py              電腦端網頁控制台（RTSP 轉 MJPEG + MQTT 代發）
    settings.example.py      設定範本 → 複製成 settings.py 再填自己的
    index.html, login.html   網頁介面
```

## 韌體怎麼用

1. Arduino IDE 裝好 ESP32 開發板套件與 **PubSubClient** 程式庫。
2. `secrets.h.example` 複製成 `secrets.h`，填入 Wi-Fi、MQTT broker 與自己的 topic 前綴。
3. 開發板選 ESP32 Dev Module 之類（作者用 `esp32:esp32:esp32doit-devkit-v1`），上傳。
4. 開序列埠監看（115200）確認有連上 Wi-Fi 與 broker。

## 網頁控制台怎麼用

```
pip install opencv-python paho-mqtt
cp web/settings.example.py web/settings.py    # 填入設定
python web/door_web.py
```

瀏覽器開 <http://localhost:8000>（**直接打開 .html 檔不會動**，一定要走這個網址）。
同一個 Wi-Fi 的手機改用電腦的區網 IP。沒有攝影機就把 `CAMERA_RTSP` 留著不管，
畫面區塊會顯示連不到，按鈕照樣能用。

## 接線

| ESP32 | 接到 | 用途 |
|---|---|---|
| D25 | 繼電器 IN1 | 開門 |
| D26 | 繼電器 IN2 | 停止 |
| D27 | 繼電器 IN3 | 關門 |
| VIN / GND | 繼電器 VCC / GND | 5V 供電，務必共地 |

繼電器只用 **NO（常開）** 與 **COM**，NC 不接；三個 COM 併接到鐵捲門主板的 GND，
NO1/NO2/NO3 分別接開門、停止、關門三個訊號腳。這樣 ESP32 沒電或當機時接點都是斷開的。

**你的主板腳位不會和作者的一樣**，動手前先查自己那台的說明書或絲印，
並用萬用表確認「短路到 GND 就等於按一下按鈕」。

## 安全提醒

- `secrets.h` 與 `settings.py` 含密碼，**不要上傳到 GitHub 或公開分享**。
- 別用不需要帳密的公開 broker：任何人猜到你的 topic 就能開你家的門。
- topic 前綴自己取一段別人猜不到的字串。
- 網頁控制台只在自己的區網內使用，不要為了在外面用而在路由器上對外開埠。

## 防誤動作機制（韌體內建）

1. 開機先把腳位壓成「放開」再切成輸出，開機不會送出觸發脈衝
2. clean session，不接收離線期間累積的指令
3. 連線後主動清掉控制 topic 上殘留的 retain 訊息
4. 連線後 3 秒內不執行任何指令
5. 同一指令 1.5 秒內重複送達只執行一次
6. 三路互鎖，`loop()` 每一圈都把不該吸合的腳位壓回去
7. Wi-Fi 斷線期間強制全部放開

授權：可自由取用修改。動到自家鐵捲門與 110V 線路請自行評估風險，作者不負任何責任。
