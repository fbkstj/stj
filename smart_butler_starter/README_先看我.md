# 智慧管家系統｜學生實作程式包（參考版）

把長照監護、AI 對話與家電控制、家人留言板、智慧監視器，整合成一套在 Windows 上運作的居家智慧管家，
再加上用藥提醒、每日平安回報、一鍵求救、作息異常偵測，並能長時間穩定運作。

完整教學（架構、功能規格、L0～L19 關卡提示語、測試、評分）：
https://fbkstj.github.io/stj/#page/smart_butler_project_guide

這個程式包是手冊 L0～L15 的**參考做法**，全部都能在不開攝影機、不送 Discord、不接真實家電的情況下執行：
影像用程式畫的火柴人示範影片，Discord 預設是「模擬模式」（只印在畫面與寫進紀錄檔）。

> **安全與隱私**
> - 金鑰、Webhook、Token 只放 `.env`，不可寫進程式、不可上傳、不可貼到對話框。外洩就到 Discord 刪除重發。
> - 開啟真實攝影機、麥克風、正式 Discord 頻道、真實家電之前，要先取得家人與老師同意。門口攝影機要貼告示。
> - 這是教學原型，只能**輔助**照顧，不能取代人的照顧、醫療判斷或 119。

## 一、安裝
0. AI 助手（擇一）：Claude Code，或 Google Antigravity。手冊的提示語兩者通用。
1. 安裝 Python 3.11 以上（勾選 **Add python.exe to PATH**）。
2. 雙擊 `0_install.bat` 安裝套件（約 1～3 分鐘）。
   想用虛擬環境：`py -m venv .venv` → `.venv\Scripts\activate` → `pip install -r requirements.txt`。
3. 雙擊 `1_make_demo.bat` 產生示範影片與假作息資料。

## 二、操作順序
| 檔案 | 說明 |
|---|---|
| `0_install.bat` | 安裝套件（第一次） |
| `1_make_demo.bat` | 產生示範影片（長照 66 秒、門口 60 秒）與 10 天假作息資料 |
| `2_run_tests.bat` | **先執行這個**：自動測試 L1～L14 與金鑰檢查，應為「通過 69 項，失敗 0 項」 |
| `3_demo_run.bat` | 示範模式跑 3 分鐘，並打開管理介面 http://127.0.0.1:8765 （主程式視窗按 F9＝求救、q＝結束） |
| `4_chat.bat` | 在視窗裡用文字和管家說話（打開客廳燈、客廳暗一點、打開電暖器、我吃藥了、救命） |
| `5_notify_test.bat` | 檢查設定與 `.env`，送出資訊／注意／緊急三則測試通報 |
| `6_analyze_videos.bat` | 不啟動系統，直接分析兩支示範影片（跌倒、久未活動、來訪次數） |
| `7_daily_and_routine.bat` | 產生今天的平安回報；用 10 天假資料檢查作息異常 |

示範模式的預期結果（`3_demo_run.bat`）：
- 啟動後 20、45 秒：Discord 新留言（女兒、兒子）；第 50 秒那則重複的留言**不會**再出現一次
- 長照影片第 26.7 秒：🚨 緊急「疑似跌倒」附截圖；沒人按「已處理」，30 秒後重送（示範模式縮短）
- 長照影片第 50 秒：⚠️ 注意「長時間沒有活動」（示範模式 12 秒就算）
- 門口影片：3 次來訪（第 3 位中間走出畫面 1.5 秒，仍算同一次）
- 啟動 30 秒：提醒「測試用藥」；1 分鐘沒按「已服藥」→ ⚠️ 注意
- 作息假資料：只有 9/9 被提醒（10:30 還沒起床、下午活動偏少），其他日子沒有誤報

## 三、接上真正的 Discord（先用練習伺服器）
1. 複製 `.env.example` 並改名成 `.env`（用記事本開啟）。
2. Discord 練習伺服器 → `#測試通報` 頻道設定 → 整合 → Webhook → 新增 → 複製網址，貼在 `DISCORD_WEBHOOK_TEST=` 後面。
   `#留言板` 頻道同樣做一個，貼在 `DISCORD_WEBHOOK_BOARD=`。
3. `config/settings.yaml` 的 `discord: dry_run:` 改成 `false`（示範模式另外看 `config/demo_overrides.yaml`）。
4. 雙擊 `5_notify_test.bat`，測試頻道應收到三則格式不同的訊息。
5. 要讀取 Discord 上的留言：在 Discord Developer Portal 建立 Bot、開啟 Message Content Intent、邀請進伺服器，
   把 Token 貼在 `DISCORD_BOT_TOKEN=`，並把留言板頻道 ID 填在 `settings.yaml` 的 `board_channel_id`。

## 四、檔案
| 檔案 | 用途 | 關卡 |
|---|---|---|
| `docs/專案規則.md`、`PROGRESS.md` | 規則檔與進度檔（每一關開頭都讓 AI 先讀） | L0 |
| `config/settings.yaml`、`core/config.py` | 所有可調參數、讀取與檢查（錯誤會指出哪個欄位） | L1 |
| `core/events.py`、`core/store.py` | 事件格式、事件匯流排、SQLite 紀錄、匯出 CSV | L2 |
| `core/notify.py` | Discord 通報分級、緊急重送、斷網先存後補 | L3 |
| `main.py`、`core/module.py`、`core/supervisor.py` | 主程式、模組基底類別、當掉自動重啟 | L4 |
| `modules/care/` | 跌倒與久未活動（`monitor.py` 是判斷規則） | L5 |
| `modules/chat/` | 意圖辨識、模擬家電、AI 閒聊（Claude API） | L6 |
| `modules/board/` | 留言板雙向同步、避免迴圈 | L7 |
| `modules/camera/` | 來訪合併、訪客查詢、隱私模式 | L8 |
| `web/` | 本機管理介面（只綁定 127.0.0.1） | L9 |
| `modules/meds/`、`daily/`、`sos/`、`routine/` | 用藥提醒、每日平安回報、一鍵求救、作息異常 | L10～L13 |
| `core/health.py`、`scripts/*.ps1` | 健康檢查、清除過期資料、開機自動啟動 | L14 |
| `tests/` | 自動測試（`run_all_tests.py`） | L15 |
| `demo/` | 示範影片產生器、答案檔、模擬 Discord 留言、假作息資料 | 全部 |

## 五、改成真實環境時要換的地方
- **人物偵測**：`core/media.py` 的 `BlobDetector` 用「和空場景相減」，只適合示範影片（背景固定）。
  真實攝影機請改用 MediaPipe 姿態偵測（跌倒）或 YOLO（訪客），只要一樣回傳「人的外框」，後面的判斷規則不用改。
- **家電**：`modules/chat/devices.py` 的 `SimDevices` 換成真實智慧插座的類別（介面一樣是 `apply(name, action)`）。
- **求救按鈕**：目前用主程式視窗的 F9 鍵模擬；實體按鈕可以用 USB 按鍵或 ESP32 送訊號。
- **開機自動啟動**：`powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1`（移除用 `remove_autostart.ps1`）。

## 六、還沒實測的部分
真實 Discord Webhook 與 Bot、Claude API 閒聊、Windows 語音念提醒、開機自動啟動，都只寫好程式、沒有在實機上測過；
第一次使用時請照上面的步驟，一項一項測試並記錄結果。
