# 導盲磚占用偵測：學生實作程式包

用一顆 USB 網路攝影機，偵測導盲磚上是否停了機車、腳踏車或堆了雜物，持續占用時發出提醒並留下紀錄。

完整教學（流程、硬體、驗證、評分）：https://fbkstj.github.io/www/#page/tactile_paving_project_guide

## 一、安裝
0. AI 助手（擇一）：Google Antigravity（免費，https://antigravity.google/download ），或 Claude Code（需 Claude 付費方案；Claude 桌面版的「Code」分頁，或 PowerShell 執行 `irm https://claude.ai/install.ps1 | iex`）。手冊裡的提示語兩者都能直接使用。
1. 安裝 Python 3.10 以上版本（安裝時勾選 **Add Python to PATH**）。
2. 在這個資料夾開啟命令提示字元，執行：
   ```
   pip install -r requirements.txt
   ```
3. 第一次執行時，程式會自動下載 YOLO11 Nano 模型（約 6 MB），請保持連線。

## 二、先用練習影片熟悉流程
雙擊 `0_demo_practice.bat`：
1. 產生 60 秒的練習影片 `demo.mp4`（車輛停放、行人經過、紙箱遮擋）。
2. 執行偵測，視窗會顯示導盲磚區域與狀態（CLEAR／OCCUPIED／ALERT），按 q 可提早結束。
3. 自動計算準確率，並產生報表 `output_demo/report.html`。

## 三、實際場地使用
| 步驟 | 檔案 | 說明 |
|---|---|---|
| 1 | `1_setup_roi.bat` | 在畫面上點出導盲磚的四個角，按 s 儲存 |
| 2 | `2_tune_color.bat` | 導盲磚淨空時執行，調整黃色範圍，按 s 儲存（同時記錄基準值） |
| 3 | `3_run_monitor.bat` | 開始偵測；紀錄存在 `output/` |
| 4 | `4_make_report.bat` | 產生 `output/report.html` 報表 |

要評估準確率時：用影片當來源（把 `config.json` 的 `source` 改成影片檔名），
在 `ground_truth.csv` 填入真實被占用的時段，執行偵測後再執行 `python evaluate.py`。

## 四、config.json 重要設定
| 設定 | 預設 | 說明 |
|---|---|---|
| `source` | `0` | 攝影機編號（外接鏡頭常是 1），或影片檔名 |
| `vehicle_classes` | 機車、腳踏車、汽車等 | 要算成「占用」的物件類別 |
| `overlap_threshold` | 0.3 | 車輛下半部有多少比例在導盲磚上才算占用 |
| `blocked_ratio` | 0.5 | 黃色比例低於基準值的幾成，就算被雜物擋住 |
| `occupy_seconds` | 30 | 持續占用幾秒才發出警示（實際場地可改 180） |
| `clear_seconds` | 5 | 淨空幾秒才算事件結束 |
| `voice_alert` | true | 是否用電腦喇叭念出提醒 |
| `blur_privacy` | true | 截圖是否對行人與車牌位置打馬賽克（請保持開啟） |
| `serial_port` | null | 選配：ESP32 的序列埠，例如 `"COM5"`（需 `pip install pyserial`） |
| `line_push` | false | 選配：LINE 通知，權杖請設在環境變數 `LINE_CHANNEL_TOKEN`、`LINE_TO` |

## 五、選配：ESP32 現場警示燈
用 Arduino IDE 把 `esp32_alert/esp32_alert.ino` 燒錄到 ESP32，接上 LED 與主動式蜂鳴器（只用低壓元件），
再把 `config.json` 的 `serial_port` 改成 ESP32 的 COM 埠。

## 六、隱私與安全
- 拍攝公共區域前，要先取得學校同意，並在現場張貼告示。
- 不要長期保存原始影片；截圖一律打馬賽克，不公開車牌與人臉。
- 紀錄只用於改善導盲設施，不作為檢舉或公開個人的用途。
- 架設鏡頭與延長線時，不要擋到通道，也不要讓線材絆倒行人。
