# AI 守望：公共場所 AI 監控通報｜學生實作程式包

用網路攝影機加上 YOLO 影像辨識，做出「發現危險 → 確認 → 通報」的監控系統：
判斷有沒有人手持危險物品、倒地、人群奔逃或異常聚集，持續一段時間才成立警示，
高風險事件給保全 5 秒按鈕取消誤報，最後用 LINE 通報；現場的 ESP32 警示盒用燈號、蜂鳴器與 TFT 文字顯示狀態。

完整教學（功能設計、演練錄影、原理、12 週流程、測試、評分）：https://fbkstj.github.io/www/#page/ai_guardian_project_guide

> **安全規定**：演練「手持危險物品」一律用**剪刀或道具**代替（刀尖朝下、不揮動），禁止攜帶真刀進教室；
> 倒地要在軟墊上、奔跑要在空曠處並有老師在場。
>
> **法律規定**：只能連線自己的或已取得授權的攝影機（未經同意連線他人攝影機，觸犯《刑法》第 358 條）。
> 拍攝他人要遵守《個人資料保護法》：取得同意、設置錄影告示、只用在安全用途、專題結束後刪除影片與截圖。
>
> 這是教學原型，只能**輔助**人員判斷，不能取代保全、警察或 110。

## 一、安裝
0. AI 助手（擇一）：Google Antigravity（免費），或 Claude Code（需 Claude 付費方案）。手冊的提示語兩者通用。
1. 安裝 Python 3.10 以上版本（勾選 **Add python.exe to PATH**）。
2. 在這個資料夾的網址列輸入 `cmd` 按 Enter，執行：`pip install -r requirements.txt`（第一次會下載 PyTorch，約 5～10 分鐘）。
   想用虛擬環境：`py -m venv .venv` → `.venv\Scripts\activate` → 再安裝；之後都要在啟用虛擬環境的視窗裡執行 bat。
3. 第一次執行會自動下載 YOLO 模型 `yolov8n.pt`（約 6 MB），需要網路。
4. 做警示盒才需要：安裝 Arduino IDE 與 ESP32 開發板套件，在程式庫管理員安裝
   「Adafruit ST7735 and ST7789 Library」與「Adafruit GFX Library」，開啟 `system/esp32_guard_alarm/esp32_guard_alarm.ino`，
   開發板選「ESP32 Dev Module」後上傳。

## 二、操作順序
| 檔案 | 說明 |
|---|---|
| `0_demo_practice.bat` | **先執行這個**：不用攝影機，檢查規則（47 項）→ 產生練習資料 → 算出成績表 |
| `1_camera.bat`～`5_alert.bat` | 程式學習關卡 L1～L5（雙擊用 0 號攝影機；把影片拖到 bat 上改用影片；視窗裡按 `q` 離開） |
| `6_line_test.bat` | 關卡 L6：發一則 LINE 測試訊息（要先設定金鑰，見下方） |
| `7_monitor_wall.bat` | 關卡 L7：多路監控牆＋警示盒（先編輯 `system/sources_config.py`；這個 bat 不發 LINE） |
| `8_label_video.bat` | **把演練影片拖到這裡**：事件開始、結束各按一次，存成 `影片名_truth.csv` |
| `9_analyze_video.bat` | **把演練影片拖到這裡**：YOLO 分析、標註影片與警示截圖（人已打馬賽克）；有答案就算成績 |
| `10_batch_evaluate.bat` | 評估 `videos/` 裡每支有答案的影片，輸出成績表 |
| `11_param_experiment.bat` | 參數實驗：換不同門檻比較偵測率與誤報（不會改到程式） |
| `12_test_alarm_box.bat` | 測試警示盒：依序顯示每種燈號與 TFT 畫面，並檢查取消鈕 |
| `13_make_scenario_video.bat` | （教師用，需要 ffmpeg）重新產生動作要求示意影片 `output/scenario_demo.mp4` |

練習資料的預期結果：6 件事偵測到 5 件（漏掉遠處低信心度的剪刀）、誤報 1 次（有人從桌上的剪刀旁走過）、
重複警示 1 次、平均反應 2.18 秒。參數實驗：`WEAPON_SUSTAIN_SEC` 改 2 秒誤報變 0 次但反應變慢；
`WEAPON_CONF` 改 0.25 會抓到全部 6 件，但手機被當成刀，誤報變 2 次。

## 三、LINE 金鑰
LINE Notify 已在 2025 年 3 月停止服務，要改用 LINE Messaging API 的官方帳號（申請步驟見網頁手冊關卡 L6）。
金鑰就是密碼：**不要寫進程式、不要貼到群組、不要上傳到網路**。用環境變數設定：
```
set LINE_TOKEN=貼上你的 Channel access token
python step6_line.py
```
完整系統要發 LINE：同一個視窗 `cd system`，再執行 `python monitor.py`（不加 `--no-line`）。

## 四、檔案
| 檔案 | 用途 |
|---|---|
| `step1～step6_*.py`、`tw_text.py`、`guard_core.py` | 程式學習關卡 L1～L6 |
| `system/monitor.py` | 關卡 L7 主程式：監控牆、警示盒（`--no-line`、`--serial COM3`、`--set 名稱=值`、`--headless --seconds 30`） |
| `system/sources.py`、`sources_config.py` | 影像來源（USB 攝影機、RTSP、公開快照、影片、圖片） |
| `system/threat_rules.py` | 持械、奔逃、倒地、聚集四種規則；**所有門檻都在檔案最上方** |
| `system/alerter.py` | 截圖、CSV、分級通報、取消窗口、冷卻時間 |
| `system/alarm_link.py` | 警示盒的狀態與序列通訊（`S<狀態><事件><秒數>`、取消鈕 `K`） |
| `system/line_*.py` | LINE 推播（獨立行程、http.client；金鑰只讀環境變數） |
| `system/analyze_video.py` | 分析影片 → 偵測紀錄 `影片名_dets.csv` → 警示片段 |
| `system/label_events.py` | 標記正確答案 |
| `system/evaluate.py`、`batch_eval.py` | 重播規則、比對答案、成績表、參數實驗（`--set`、`--sweep`） |
| `system/demo_scenes.py`、`make_demo_detections.py` | 練習資料（3 分鐘穿堂演練的模擬偵測結果） |
| `system/test_rules.py` | 不用攝影機的規則與工具測試 |
| `system/esp32_guard_alarm/` | ESP32 警示盒韌體；`make_tft_labels.py` 產生 TFT 中文（改文字要重新執行再上傳） |
| `system/test_alarm.py` | 警示盒硬體測試 |
| `system/make_scenario_video.py` | 動作要求示意影片 |

資料夾：`videos/` 自己的演練影片、答案與偵測紀錄（**不要上傳**）；`logs/` 警示片段；
`output/` 成績表、參數比較表、標註影片與截圖；`system/events/` 監控牆的事件截圖與紀錄（**定期刪除**）。

`threat_rules.py` 的 `PRACTICE_SCISSORS = True` 會把剪刀當成危險物品，方便上課練習；正式展示時改成 `False`。

## 五、限制
- 模型用 COCO 資料集訓練，**沒有槍、火焰、煙霧**類別，要偵測這些得自己蒐集資料訓練。
- 小模型（yolov8n）在遠距離、低解析度下不容易認出刀具與剪刀，鏡頭要近、背景要單純。
- 「手持」只看框有沒有重疊：有人從放著剪刀的桌子旁走過也會被當成手持（練習資料的誤報就是這樣來的）。
- 「倒地」用人框的長寬比判斷，比較粗略；延伸挑戰可以改用姿態辨識。
- 標註影片只遮住**有被偵測到**的人，對外使用前仍要逐張檢查。
- 手機上的「國家級警報」（細胞廣播）只有政府機關能發送，民間系統不能串接。
