# 頭部障礙物警示帽：學生實作程式包

白手杖探不到頭部與胸口高度的障礙物（招牌、樹枝、貨車後照鏡）。這個專題在帽子上裝鏡頭與雷射測距，
筆電放在背包裡辨識前方物體，用震動與骨傳導耳機提醒使用者。

完整教學（接線、流程、測試、評分）：https://fbkstj.github.io/www/#page/headgear_assist_project_guide

> 這是教學用的輔助原型，只能在封閉場地、有保護者陪同下測試，不能取代白手杖、導盲犬或定向行動訓練。

## 一、安裝
0. AI 助手（擇一）：Google Antigravity（免費），或 Claude Code（需 Claude 付費方案）。手冊的提示語兩者通用。
1. 安裝 Python 3.10 以上版本（勾選 **Add Python to PATH**）。
2. 在這個資料夾開啟命令提示字元：`pip install -r requirements.txt`
3. 安裝 Arduino IDE 與 ESP32 開發板套件；程式庫管理員搜尋「VL53L1X」安裝 **Pololu** 版。
4. 用 Arduino IDE 開啟 `esp32_headgear/esp32_headgear.ino`，開發板選「ESP32 Dev Module」，上傳。
5. Windows 需要中文語音：設定 → 時間與語言 → 語音 → 新增「中文（台灣）」語音。

## 二、操作順序
| 檔案 | 說明 |
|---|---|
| `0_demo_practice.bat` | 還沒做好帽子時，用練習影片與模擬距離測試程式（會開視窗） |
| `1_test_sensors.bat` | 測試 ESP32、兩顆 ToF 與震動馬達（按 Enter 震動，輸入 q 離開） |
| `2_test_camera.bat` | 不接 ESP32，只測鏡頭與辨識（視窗中按 b 描述前方、q 離開） |
| `3_start_assist.bat` | 正式使用：聽到「系統啟動完成」後，再闔上筆電放進背包 |
| `4_evaluate_trials.bat` | 分析 `trials.csv` 的障礙路線測試結果 |

`trials_example.csv` 是格式範例（數字不是實測結果），可以用 `python evaluate_trials.py trials_example.csv` 練習。

## 三、筆電放進背包前
- **闔上螢幕不要睡眠**：控制台 → 電源選項 → 選擇闔上螢幕時的行為 → 「使用電池」與「一般電源」都選「不執行任何動作」。
- 關閉自動更新重新開機、螢幕保護程式；電源模式選「最佳效能」。
- 背包要透氣，筆電直立放在有隔層的位置，不要和行動電源、水壺擠在一起；使用後摸摸看是否過熱。
- 帽子的兩條 USB 線（鏡頭、ESP32）用魔術帶沿背帶固定，接頭處留一點鬆弛，避免轉頭時被扯掉。

## 四、config.json 重要設定
| 設定 | 預設 | 說明 |
|---|---|---|
| `camera` | 0 | 鏡頭編號（筆電內建鏡頭常是 0，帽子上的外接鏡頭可能是 1） |
| `serial_port` | auto | ESP32 序列埠；自動找不到時改成例如 `"COM5"` |
| `near_mm` | 800 | ToF 距離小於這個值就用語音提醒「很近」 |
| `approach_ratio` | 1.4 | 人、車在 1 秒內畫面面積變大幾倍算「靠近」 |
| `repeat_cooldown_sec` | 4 | 同一種提醒至少隔幾秒才再說一次 |
| `detect_interval_sec` | 0.3 | 每隔幾秒辨識一次；筆電較慢可改 0.5 |

震動的距離門檻寫在 ESP32 程式開頭（`DIST_NEAR`、`DIST_MID`、`DIST_FAR`）。

## 五、紀錄與隱私
- 每次執行會在 `logs/` 產生一個 CSV，記錄每次提醒的時間、距離與內容，可以用來分析誤報。
- 程式**不錄影、不存照片**；測試時若要錄影說明，要先取得入鏡者同意。
