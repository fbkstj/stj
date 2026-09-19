# 自行車「後方來車」警示：學生實作程式包

騎單車時看不到後方逼近的大車。這個專題用朝後拍攝的影片，讓 YOLO 找出汽車、機車、公車、貨車，
再從車框「變大的速度」估計還有幾秒會到，提早亮燈、發出嗶聲，並用語音說出「後方機車／汽車／大型車」，
TFT 螢幕同時顯示警示等級、車種與到達秒數。

完整教學（功能設計、拍攝方法、原理、流程、測試、評分）：https://fbkstj.github.io/www/#page/bike_rear_alert_project_guide

> **安全第一**：請用錄好的影片或桌上模型測試，**不要邊騎車邊測試或看螢幕**。這是教學原型，不能取代後照鏡、車燈、安全帽等正規安全裝備。

## 一、安裝
0. AI 助手（擇一）：Google Antigravity（免費），或 Claude Code（需 Claude 付費方案）。手冊的提示語兩者通用。
1. 安裝 Python 3.10 以上版本（勾選 **Add Python to PATH**）。
2. 在這個資料夾開啟命令提示字元：`pip install -r requirements.txt`
3. 第一次執行會自動下載 YOLO 模型 `yolo11n.pt`（約 5 MB），需要網路。
4. 桌上模型展示才需要：安裝 Arduino IDE 與 ESP32 開發板套件，在程式庫管理員安裝
   「Adafruit ST7735 and ST7789 Library」與「Adafruit GFX Library」，開啟 `esp32_rear_alert/esp32_rear_alert.ino`，
   開發板選「ESP32 Dev Module」後上傳（DFPlayer 不需要另外裝程式庫）。
5. 語音檔已經放在 `sd_card/01/`（001～009.wav）。接 DFPlayer 時，把整個 `01` 資料夾複製到 microSD 卡
   （FAT32 格式，32 GB 以下）的根目錄。想重新產生或改用自己的聲音，見下方「語音」。

## 二、操作順序
| 檔案 | 說明 |
|---|---|
| `0_demo_practice.bat` | 產生練習影片 → 分析 → 計算成績，確認環境沒問題 |
| `1_test_lights.bat` | 測試 ESP32 的三色燈、蜂鳴器、TFT 文字與 9 段語音 |
| `2_label_video.bat` | **把影片拖曳到這個檔案上**：播放影片，車輛經過時按鍵，在影片旁邊存成 `影片名_truth.csv` |
| `3_analyze_video.bat` | **把影片拖曳到這個檔案上**：分析一支影片（開視窗），輸出標註影片；有答案檔就順便算成績 |
| `4_batch_evaluate.bat` | 分析 `videos/` 裡每支有答案檔的影片，整理成一張成績表 |
| `5_bench_demo.bat` | 桌上模型展示：鏡頭＋ESP32 燈號、TFT、語音（沒接 ESP32 會改用電腦播放語音與嗶聲） |
| `6_make_voice_files.bat` | 用 Windows 中文語音重新產生 `sd_card/01/` 的語音檔 |
| `7_test_voice_logic.bat` | 不用硬體，檢查「什麼時候說哪一段」的規則與傳給 ESP32 的格式 |
| `8_make_scenario_video.bat` | （教師用，需要 ffmpeg）重新產生「動作要求示意影片」`output/scenario_demo.mp4` |

練習影片的預期結果：兩次逼近都有警示、沒有誤報，平均提早約 1.3 秒（第一台約 2.1 秒、第二台約 0.5 秒），
車種判斷 2/2 正確；語音依序是「後方大型車」「危險，大型車」「危險，大型車」。

### 語音
| 編號 | 內容 | 什麼時候說 |
|---|---|---|
| 001～003 | 後方機車／後方汽車／後方大型車 | 一台車第一次進入「注意」時（公車、貨車都算大型車） |
| 004 | 後方多台車 | 同時有兩台以上新的車（其中有大型車時改說「後方大型車」） |
| 005 | 危險，注意 | 升到「危險」，而且危險的車不只一種 |
| 006 | 警示系統啟動 | 程式開始時 |
| 007～009 | 危險，機車／汽車／大型車 | 每次警示第一次升到「危險」時（會打斷正在說的話） |

- 同一台車只說一次；兩段語音至少間隔 `voice_cooldown_sec` 秒。
- 想用自己的聲音：錄好 9 段（每段 1.2 秒內），轉成 WAV，照編號命名放進 `sd_card/01/`；
  改了文字要一起改 `voice.py` 的 `CLIPS`。
- 語音與蜂鳴器同時響會聽不清楚，所以播放語音時蜂鳴器會暫停約 1.2 秒。

### 標記按鍵（2_label_video.bat）
在車頭到達鏡頭旁邊、離開畫面的那一刻按：
`1` 汽車、`2` 機車、`3` 公車、`4` 貨車、`空白鍵` 不分車種；
`u` 取消上一個、`p` 暫停、`a`／`d` 倒退／快轉 3 秒、暫停時 `,`／`.` 逐格、`q` 存檔離開。

### 參數實驗（不會改到 config.json）
```
python batch_run.py videos --tag base
python batch_run.py videos --set ttc_warn=5 --tag warn5
python batch_run.py videos --set imgsz=960 --set confirm_count=1 --tag test3
```
每次結果存在 `output/summary_<標籤>_<時間>.csv`，用 Excel 開啟比較。

## 三、資料夾
| 位置 | 內容 |
|---|---|
| `videos/` | 自己拍的影片與答案檔（`影片名_truth.csv`）。**不要上傳到網路** |
| `logs/` | 每次分析的警示紀錄（CSV）與摘要（JSON）；批次分析在 `logs/batch_…/` |
| `output/` | 標註影片、成績表、`snapshots/` 警示截圖（都已模糊行人與車牌） |

## 四、config.json 重要設定
| 設定 | 預設 | 說明 |
|---|---|---|
| `ttc_warn` | 4.0 | 估計幾秒內會到達就「注意」（黃燈） |
| `ttc_danger` | 2.0 | 估計幾秒內會到達就「危險」（紅燈） |
| `zone_x` | [0.35, 1.0] | 只看畫面這個左右範圍內的車（0＝最左、1＝最右）。台灣靠右行駛，超車的車在朝後畫面的右半邊 |
| `min_width_ratio` | 0.04 | 車框寬度小於畫面寬度的幾倍就先不判斷（太遠、太不準） |
| `size_window_sec` | 0.8 | 用最近幾秒的車框變化來估計到達時間 |
| `min_points` | 4 | 至少要有幾個框才開始估計 |
| `confirm_count` | 2 | 連續幾次判定逼近才發出警示（越大誤報越少，但越慢） |
| `hold_sec` | 1.0 | 警示至少維持幾秒，避免燈號一直閃 |
| `lost_sec` | 0.8 | 車子幾秒沒被認出來，就當作離開 |
| `imgsz` | 640 | 辨識解析度；改 960 可以看到更遠的車，但比較慢 |
| `confidence` | 0.25 | YOLO 信心門檻 |
| `detect_interval_sec` | 0.1 | 每隔幾秒辨識一次；電腦慢可改 0.2 |
| `camera` | 0 | 桌上展示用的鏡頭編號（外接鏡頭可能是 1） |
| `serial_port` | auto | ESP32 序列埠；自動找不到時改成例如 `"COM5"` |
| `voice` | true | 是否說出車種（ESP32 的 DFPlayer，或沒接 ESP32 時用電腦播放） |
| `voice_volume` | 22 | DFPlayer 音量（0～30） |
| `voice_cooldown_sec` | 1.5 | 兩段語音至少間隔幾秒 |
| `big_vehicle_classes` | bus、truck | 哪些車種算「大型車」 |
| `privacy_blur` | true | 輸出影片與截圖時，把行人和車輛下半部（車牌）模糊 |
| `snapshot_on_alert` | true | 每次警示開始或升級時存一張截圖 |

## 五、拍攝影片注意事項
- **最安全的做法**：在人行道或路邊安全位置架腳架，鏡頭朝向來車方向拍攝，不要站在車道上。
- 如果要把鏡頭裝在自行車後方實際騎乘錄影，要經老師同意、在車少的路段、戴安全帽，騎車時**不看手機或螢幕**。
- 鏡頭要固定牢靠、水平，拍到的畫面要包含後方車道；建議 1080p、30fps。
- 影片裡有車牌和路人，**不要把原始影片上傳到網路**；報告與展示請用 `output/` 裡已模糊的影片或截圖。

## 六、程式檔案
- `rear_alert.py`：主程式（辨識、追蹤、估計到達時間、警示狀態、燈號、紀錄、截圖）
- `label_events.py`：標記正確答案
- `evaluate.py`：比對一支影片，算出提早秒數、漏報、誤報、各車種成績
- `batch_run.py`：批次分析與參數實驗
- `make_demo_video.py`：產生練習影片 `videos/demo.mp4` 與答案 `videos/demo_truth.csv`
- `voice.py`：語音規則（什麼時候說哪一段）與傳給 ESP32 的狀態格式
- `test_voice_logic.py`：不用硬體的語音規則測試
- `make_voice_files.py`：產生語音檔 `sd_card/01/001～009.wav`
- `make_scenario_video.py`：產生動作要求示意影片（情境動畫＋語音＋嗶聲，規則與程式相同）
- `make_tft_labels.py`：把 TFT 要顯示的中文轉成點陣圖（`esp32_rear_alert/tft_labels.h`）；改了顯示文字要重新執行再上傳
- `test_lights.py`：測試 ESP32 燈號、TFT 與語音
- `esp32_rear_alert/`：ESP32 程式（綠燈＝安全、黃燈閃＝注意、紅燈快閃＝危險、綠燈慢閃＝沒收到電腦訊號；
  TFT 顯示等級、車種、到達秒數；DFPlayer 播放語音）

## 七、ESP32 接線
| 元件 | 接法 |
|---|---|
| 綠／黃／紅 LED | GPIO25／26／27 → 220Ω → LED → GND |
| 主動式蜂鳴器模組 | VCC→3V3、GND→GND、I/O→GPIO14（高電位觸發） |
| ST7735 1.8 吋 TFT | SCK→GPIO18、SDA→GPIO23、CS→GPIO5、A0(DC)→GPIO21、RST→GPIO22、VCC→3V3、GND→GND、LED→3V3 |
| DFPlayer Mini | VCC→5V（VIN）、GND→GND、RX←1kΩ←GPIO17、TX→GPIO16、SPK_1／SPK_2→喇叭（3W、4～8Ω） |

TFT 顏色或邊緣不對時，把程式裡的 `INITR_BLACKTAB` 改成 `INITR_GREENTAB` 或 `INITR_REDTAB`。

### ESP32 通訊格式（每行一個，最多 8 個字元）
| 指令 | 意義 |
|---|---|
| `S1B25` | 狀態：S＋等級（0／1／2）＋車種（M 機車、C 汽車、B 大型車、N 無）＋到達秒數×10 |
| `P1`～`P9` | 播放 microSD 卡 `01` 資料夾的 001～009 號語音 |
| `V0`～`V30` | 語音音量 |
| `L0`～`L2` | 舊版狀態（只有等級），仍然可以用 |
