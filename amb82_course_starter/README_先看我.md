# AMB82-Mini 影像物聯網入門：課程程式包

115 年 12 月 2 日研習用。六個單元的範例程式、Google Apps Script 接收端，以及三支「先在電腦上確認環境」的小工具。

完整講義（每個步驟、畫面、排錯）：https://fbkstj.github.io/www/#page/amb82_iot_course_guide

## 一、課前準備（請務必先做完）
1. **Arduino IDE 2.x**（arduino.cc 下載安裝）。
2. **開發板套件**：檔案 → 偏好設定 → 額外的開發板管理員網址，貼上
   `https://github.com/ambiot/ambpro2_arduino/raw/main/Arduino_package/package_realtek_amebapro2_index.json`
   再到開發板管理員搜尋 **AmebaPro2** 安裝（約 2 GB，請先在家裝好）。
   開發板選 **AMB82-MINI**。
3. **TFT 才需要**：準備 **ILI9341** 介面的 TFT 模組。函式庫（`AmebaILI9341`）已內建在開發板套件裡，不必另外安裝。
   （Adafruit 的 ST7735 函式庫在這塊板子上編譯不過，不要用。）
4. **microSD 卡**：FAT32 格式（32 GB 以下最穩）。
5. **帳號**：Google 帳號；想做 Telegram 的先在手機裝 Telegram；想做 LINE 推播的先申請 Messaging API channel。
6. **BlocklyDuino F2**：依講師提供的版本安裝；積木產生的程式碼可以和本程式包互相對照。

## 二、六個單元
| 資料夾 | 單元 | 做出什麼 |
|---|---|---|
| `01_camera_snapshot/` | 第 1 節：認識板子 | 每 5 秒拍一張存 SD 卡，LED 閃一下 |
| `02_rtsp_stream/` | 第 2 節：RTSP 串流 | 用 VLC 看板子的即時影像 |
| `03_ap_web_snapshot/` | 第 3 節：AP 模式網頁 | 手機連上板子的 WiFi，看即時畫面、開關 LED |
| `04_cloud_upload/` | 第 4 節：雲端整合 | 照片自動存到雲端硬碟、寫進試算表、推播 LINE |
| `05_record_mp4_tft/` | 第 5 節：錄影與顯示 | 按鈕錄 MP4 存 SD，TFT 顯示錄影狀態 |
| `06_telegram_bot/` | 第 6 節：遠端控制 | 手機傳 `/photo`、`/led on`、`/status` 指令控制板子 |

每支程式最上面都有「可以修改的設定」區塊，先改 WiFi 名稱與密碼再上傳。

## 三、電腦端小工具（不用板子也能先測）
| 檔案 | 用途 |
|---|---|
| `tools/rtsp_check.py` | 測 RTSP 連不連得上、抓一張畫面、量實際張數（需要 ffmpeg） |
| `tools/appscript_test.py` | 從電腦送一張測試圖，確認 Apps Script 部署成功 |
| `tools/telegram_check.py` | 確認 Bot Token 正確、找出自己的 chatID、試傳訊息 |

用法寫在每支程式最上面，例如：
```
python tools/rtsp_check.py rtsp://192.168.1.50:554
python tools/appscript_test.py https://script.google.com/macros/s/xxxx/exec
python tools/telegram_check.py
```

## 四、金鑰與隱私（很重要）
- **Bot Token、Apps Script 網址、LINE token 都等於密碼**：不要上傳到 GitHub，不要貼進報告或簡報，截圖要遮起來。
- 這個程式包裡的都是假的預設值，請自己填上，**填好的檔案不要再傳給別人**。
- 板子會拍到教室裡的人：**拍攝前先告知**，展示影片與截圖要先取得同意，課後把雲端硬碟裡的照片刪掉。
- AP 模式、ngrok 對外開放時，任何知道網址的人都看得到畫面，**課後一定要關閉**。

## 五、常見狀況
| 狀況 | 先檢查 |
|---|---|
| 找不到 COM 埠 | 換一條「可傳輸資料」的 USB 線；確認驅動程式已安裝 |
| 上傳失敗／卡住 | 關掉序列埠監控視窗再上傳；確認開發板選 AMB82-MINI |
| 讀不到 SD 卡 | 是否為 FAT32、是否插到底、先在電腦上確認卡片正常 |
| VLC 打不開串流 | 先用 `tools/rtsp_check.py` 判斷是板子還是 VLC 的問題；學校 WiFi 常隔離裝置，改用手機熱點 |
| 上傳雲端失敗 | Apps Script 部署時「誰可以存取」要選「任何人」；改完程式要重新部署 |
| Telegram 沒反應 | 先用 `tools/telegram_check.py` 確認 Token 與 chatID；學校網路可能擋住，改用手機熱點 |
| TFT 沒畫面 | 確認是 ILI9341 模組、背光腳接 3V3、DC／RESET 腳位與程式一致 |

## 六、程式碼來源
六支程式改寫自 Realtek 官方 Arduino 範例（`Ameba-AIoT/ameba-arduino-pro2`）：
StreamRTSP、RecordMP4、CaptureJPEG、CreateWiFiAP、HttpUploadImageGoogleDrv、HttpUploadImageTelegram，
加上中文註解、設定區塊、錯誤提示與安全檢查。
