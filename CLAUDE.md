# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# stjweb — 簡老師的個人網站

楊梅高中實習處主任簡樹桐的教學網站。純靜態 HTML，沒有建置流程，每個 `.html` 各自獨立（CSS/JS 大多內嵌）。

- 正式站：https://fbkstj.github.io/stj/ （GitHub Pages，repo `fbkstj/stj`，分支 `main`；本機 remote `origin`）。2026-09-19 從 www 整站複製過來。
- 舊站：https://fbkstj.github.io/www/ （repo `fbkstj/www`，本機 remote `www`、追蹤分支 `www-main`）。使用者要把它縮減成只剩少數公開連結；要改舊站時在 `www-main` 上 commit 再 `git push www www-main:main`，不要把 main 推到 www。
  - 2026-09-19 已從 www 下架：重補修（入口頁、自學系統、9 支影片）、首頁「教學影片」選單與 KiCad／ESP32 影片卡片、「專題製作」選單＋8 張卡片＋166 個專題檔案（含 `_src/`、`tools/airtouch_sim/`）。AMB82 兩份、筆電攝影機 1 份研習講義仍保留。下一步：使用者要再決定 www 只留哪幾個連結（尚未提供清單）。
  - `www-main` 上的修改是用暫存 index（`GIT_INDEX_FILE`＋`read-tree`／`update-index`／`commit-tree`）做的，不會動到 main 的工作目錄；這樣做可以避免把 www 分支整個 checkout 出來。
- 備用站：https://stjwww.netlify.app/
- 本機測試：`python serve.py` → http://127.0.0.1:18456/ （Python 3.14 全域安裝於 `C:/Python314`，需 PyMuPDF）。`.claude/launch.json` 已設定好，在 Claude Code 用 `preview_start` 名稱 `stjweb` 即可啟動。

## 主要頁面

| 檔案 | 內容 |
|---|---|
| `index.html` | 入口首頁（側欄導覽，連到下列各頁） |
| `digi_el.html` | 數位電子乙級評審表設定，呼叫 `serve.py` 的 `/api/generate_pdf` 產生 PDF |
| `cpld_simulator.html`、`pcb_layout.html`、`CPLD/` | 數位電子乙級 CPLD 模擬器、PCB 佈線工具、題目資料 |
| `roster.html` | 實習處輪值表系統 |
| `coursemap*.html` | 各學年度（110、112–115）課程地圖；`premium` 是另一種版型 |
| `arduino.html`、`app_inventor*.html`、`fpga_keypad.html`、`instrument*.html` 等 | 各科教材 |
| `ai_vision_course_guide.html`、`mcp_course_automation_guide.html`、`teaching_video_pipeline_guide.html` | AI 研習手冊 |
| `airtouch_*.html` | AirTouch 專題展示與競賽報告 |
| `ymhs_calendar.js/.json` | 學校行事曆資料，由 `update_calendar.py` 從學校 Google 日曆抓取產生 |

## 工具腳本

- `serve.py`：本機靜態伺服器（port 18456），加上 `/api/generate_pdf`。這支 API **只在本機能用**，GitHub Pages 上跑不了。
- `update_calendar.py`：更新 `ymhs_calendar.json` / `.js`。
- `build_map.py`、`build_map2.py`：合併各學年度課程地圖。它們讀的是 `web/` 子資料夾，但這個資料夾已經不存在，要用的話得先改路徑。
- `skills/`：教學影片後製、MCP 研習自動化等技能包的原始檔。
- 根目錄的 `process_1150907_ai_course.py`、`render_all_and_launch_upload.py`、`upload_remaining_episodes_and_playlist.py`、`deep_examine_and_rebuild.py`、`exchange_code_direct.py` 與 `run_pipeline.bat`、`一鍵自動化執行.bat` 是某次課程影片剪輯＋YouTube 上傳的一次性腳本（faster-whisper、OpenCC、YouTube API，會讀 `client_secrets.json`/`yt_token.json`），跟網站本身無關。兩個 bat 會安裝 `requirements.txt`，但根目錄沒有這個檔案。
- `chunk_8110_*`、`b64_8110.txt` 是早期傳檔留下的暫存分段，仍被 git 追蹤，網頁沒有用到。

## 推送（重要）

- 完整流程寫在 `.claude/skills/push/SKILL.md`（`/push`），推送前一律照它檢查。

- 直接執行 `git push` 可能卡住：Git Credential Manager 的登入視窗在背景跳不出來（詳見 `GIT_PUSH_NOTES.md`）。使用者要求推送時，改用 `GCM_INTERACTIVE=never GIT_TERMINAL_PROMPT=0 timeout 90 git push origin main`，已存好的憑證可以直接用（2026-09-16 驗證成功），失敗也不會卡住。失敗時再請使用者雙擊 `一鍵推送到GitHub.bat` 或 `deploy.bat`。不要用 `--force`。
- 這兩個 bat 都會 `git add .` 並 `git push --force`。commit 之前先看 `git status`，確認沒有夾帶機密或不該上傳的檔案。

## 智慧管家系統開發手冊（2026-09-19）

- `smart_butler_project_guide.html`（網址 https://fbkstj.github.io/stj/#page/smart_butler_project_guide ）：**直接編輯這個檔案**，沒有範本或產生腳本；版面樣式沿用 `ai_guardian_project_guide.html`。已連到首頁「專題製作」選單與首頁卡片，並登記在 `遠端網址備忘.txt`。
- 內容：00 使用方式（含「使用 Antigravity」注意要點與開頭段落）、01～05 概要／架構圖／規格 F1～F20／環境／16 週、06 關卡 L0～L15、延伸關卡 L16～L19（地震颱風平安確認、防詐提醒、醫療資訊卡與交班、毫米波雷達）、07 共通提示語（★ Aina 整合版提示語＋逐段說明表）、08 測試 T1～T20、09 隱私倫理、10 常見問題、11 延伸挑戰、12 報告評分、教師備註。
- 情境動畫：`<figure class="sim">` 內的 SVG，元素用 `data-on="2"`／`"2-4"`／`"1,4-5"` 指定第幾步顯示，`data-shake` 指定第幾步搖晃；步驟文字寫在 `<ol class="sim-steps">`，播放器（播放／重播／分段按鈕）由頁尾 script 自動產生。新增動畫照這個格式寫即可。
- 檢核點用 `localStorage` 鍵 `smart-butler-guide-checks` 記錄。
- 這份手冊來自使用者「Aina」專題（長照監護＋Discord、AI 對話＋家電、留言板＋Discord、智慧監視器，Windows 平台）；老師接著可能要延伸更多功能或製作程式包。

## 注意事項

- **機密檔**：`client_secrets.json`、`yt_token.json` 是 YouTube API 憑證，已列在 `.gitignore`，不可 commit，也不可寫進網頁。**打包 zip 時也要排除**：`.gitignore` 管不到 zip 裡面的檔案，2026-09 曾有兩個影片技能包夾帶這兩個檔案被公開，之後已重新打包並改附 `README_憑證請自行建立.txt`。
- **加密頁面**：`app_inventor_answers.html`、`mcp_course_automation_guide.html`、`amb82_iot_course_guide.html`、`amb82_ai_course_guide.html` 是 StatiCrypt 加密後的輸出，**不要直接改**。未加密原始檔放在 `_private/`（已列入 `.gitignore`，不可 commit），改完由使用者雙擊 `_private/加密網頁.bat` 重新加密（密碼由使用者自己輸入，Claude 不經手）。MCP 頁的 SKILL zip 會以 data URI 包進加密頁面，不再單獨放在網站上。`_private/.staticrypt.json` 存鹽值，要保留，否則「記住我」會失效。
- **公開網站**：所有內容都會公開，不要放學生個資（像是身分證、電話、完整座號對照）。
- `.git` 已經約 1.3 GB，追蹤的檔案裡有 zip、mp4、7z。新的大型檔案（影片、壓縮包）盡量放 YouTube 或雲端硬碟，網頁只放連結。
- 頁面語言是 `zh-Hant-TW`，字型用 Google Fonts（Noto Sans TC / Outfit）。新頁面要比照既有頁面的風格、響應式版面，並符合無障礙 WCAG AA（對比度、alt 文字、語意標籤）。
- `ai_vision_course_guide.html` 的 Tailwind 已預先產生並內嵌在 `<style id="tailwind-build">`（不再用 cdn.tailwindcss.com），新增或修改 class 後要用 `npx tailwindcss@3.4.17` 重新產生。其他頁面仍用 CDN。
- 下載包：`ai_vision_starter_pack.zip`（AI 視覺入門，不附模型）、`airtouch_project_pack.zip`（AirTouch 展示頁用）。打包時不要放測試照片、錄音、開發紀錄或重複檔案。這兩包裡的講義 md 沒有獨立原始檔，要改得先從 zip 取出。
- 導盲磚專題：手冊 `tactile_paving_project_guide.html`，程式原始碼在 `tactile_paving_starter/`（改完要重新打包成 `tactile_paving_starter_pack.zip`，zip 內保留 `tactile_paving_starter/` 資料夾層）。測試方式：`make_demo_video.py` → `paving_monitor.py --config demo_config.json --no-window` → `evaluate.py`，執行產物已列在 `.gitignore`。
- 警示帽專題：手冊 `headgear_assist_project_guide.html`，原始碼在 `headgear_assist_starter/`（打包成 `headgear_assist_starter_pack.zip`）。ESP32 韌體可用 Arduino IDE 內附的 arduino-cli 編譯（fqbn `esp32:esp32:esp32`，需 Pololu VL53L1X 程式庫）；筆電端測試：`make_demo_video.py` → `headgear_assist.py --video demo.mp4 --fake-sensor demo_sensor.csv --no-voice`。
- 自行車後方來車專題（ai_vision 專題 04）：手冊 `bike_rear_alert_project_guide.html`（第 3 章「功能設計」的功能編號 F1～F18、測試 T1～T10 要和程式一致），原始碼在 `bike_rear_alert_starter/`（打包成 `bike_rear_alert_starter_pack.zip`，同樣保留資料夾層；排除 `logs/`、`output/`、`videos/` 裡的影片與 `yolo11n.pt`）。學生影片放 `videos/`，已列入 `.gitignore`。測試：`make_demo_video.py`（固定亂數）→ `rear_alert.py --video videos/demo.mp4 --no-serial --no-sound` → `evaluate.py --truth videos/demo_truth.csv`，預期成功 2 次、誤報 0 次、平均提早 1.30 秒、車種 2/2 正確，語音依序「後方大型車」「危險，大型車」「危險，大型車」；`batch_run.py videos` 應得到相同結果。語音規則在 `voice.py`（改了要同步 `test_voice_logic.py`，目前 23/23），語音檔 `sd_card/01/001～009.wav` 由 `make_voice_files.py` 產生並隨 zip 附上；TFT 中文是 `make_tft_labels.py` 產生的 `tft_labels.h`，改文字要重新產生。手冊第 2 章嵌入的示意影片 `bike_rear_alert_scenario.mp4`（與封面 `_poster.jpg`）由 `make_scenario_video.py` 產生（需 ffmpeg，約 20 秒；情境是事先安排的車輛動作，警示與語音規則沿用 `voice.py`），改了規則或語音要重新產生、複製到根目錄，並同步手冊裡的影片文字稿時間。改了演算法或參數，手冊與 README 裡的這些數字要一起更新。韌體 `esp32_rear_alert` 控制燈號、蜂鳴器、ST7735 TFT（需 Adafruit ST7735 and ST7789、Adafruit GFX 程式庫；ESP32 上 1.11.0 可編譯）與 DFPlayer（直接送序列指令，不需程式庫），通訊格式 `S<等級><車種><秒數×10>`、`P1～P9`、`V0～V30`，每行最多 8 字元。在 Claude Code 的 Bash 工具執行時要設 `PYTHONIOENCODING=utf-8`，否則中文輸出會亂碼（學生在 cmd 執行正常）。
- AirTouch 實作手冊：`airtouch_project_guide.html`（第 3 章功能 F1～F21、測試 T1～T12，第 8 章應用程式模式，都要和程式一致），原始碼在 `airtouch_starter/`（打包成 `airtouch_starter_pack.zip`，保留資料夾層；排除 `logs/`、`output/`、`models/`、`data/`）。程式以模組拆分：`gestures.py`（規則判斷＋觸發狀態機）、`voice_commands.py`（純文字解析）、`voice_listener.py`、`actions.py`（依 `config.json` 的 `profiles` 決定動作，`--dry-run` 不按鍵）、`ppt_com.py`（PowerPoint COM）、`airtouch.py`（`ProfileManager` 依前景視窗標題自動切換模式，`--profile` 固定）。模式比對順序就是 `profiles` 的鍵順序。PowerPoint 已安裝；放映相關功能會全螢幕佔用畫面，未經同意不要實際放映測試。不用鏡頭的測試：`make_demo_samples.py`（固定亂數）→ `evaluate_gestures.py data/demo_samples.csv`（預期 96.5%、誤觸 2.0%）、`test_voice_commands.py`（79/79）、`test_trigger.py`（14/14）、`test_profiles.py`（77/77；沒裝 pyautogui 時 71/71）；主程式可用 `--video 檔案 --dry-run --headless --text` 測試。MediaPipe 1.0 沒有 `mp.solutions`，要用 tasks API，模型用 `model_asset_buffer` 載入（路徑有中文時 `model_asset_path` 與 `cv2.imread` 會失敗）。全域 Python 沒裝 mediapipe/pyautogui，測試時用暫存 venv。**這台電腦有鏡頭，不要在未經同意下執行會開鏡頭的程式。** 「略過」只在 YouTube 顯示按鈕時代按；不要加入封鎖廣告、快轉或跳過不可略過廣告的功能（違反 YouTube 條款）。舊的 `airtouch_project_pack.zip` 與首頁 AirTouch 成果卡片仍含這類內容，是否調整由使用者決定。手冊第 2 章的情境動畫與互動模擬器由 `tools/airtouch_sim/build.py` 產生（原始碼 `sim.js`、`sim.css`、`voice_parse.js`；網頁中 `<!-- at-sim:… -->` 區塊不要手改）：改了 `airtouch_starter/config.json` 或 `voice_commands.py` 後要重跑 `python tools/airtouch_sim/build.py --check`（JS 與 Python 語音解析要 0 句不一致）。`tools/` 不放進學生程式包。
- AI 守望（公共場所 AI 監控通報）專題（ai_vision 專題 09）：手冊 `ai_guardian_project_guide.html` 是**產生出來的**，不要直接改。改文字改 `_src/ai_guardian_guide_template.html`，改程式改 `ai_guardian_starter/`，兩種都要執行 `python _src/build_ai_guardian_guide.py`（把 `{{路徑}}` 換成程式包裡的檔案內容）。章節比照自行車專題：功能 F1～F20、測試 T1～T12、通報狀態表、12 週流程，數字要和程式一致。程式包：根目錄是 L1～L6 學習關卡（`step*.py`）與 bat `0_demo_practice`～`13_make_scenario_video`；`system/` 是完整系統與工具——`threat_rules.py`（所有門檻，`set_param`/`TUNABLE` 供 `--set`、`--sweep`；`PRACTICE_SCISSORS` 把剪刀當危險物品）、`alerter.py`、`alarm_link.py`（警示盒狀態 `S<0-4><W|R|F|C|N><秒>`，取消鈕回傳 `K`）、`analyze_video.py`（YOLO → `videos/影片名_dets.csv`，`--save` 輸出整個人框馬賽克的影片與截圖）、`evaluate.py`/`batch_eval.py`（重播規則比對 `_truth.csv`）、`label_events.py`、`demo_scenes.py`＋`make_demo_detections.py`（3 分鐘模擬演練）、`esp32_guard_alarm/`（韌體，GPIO25/26/27 燈、14 蜂鳴器、4 取消鈕、ST7735；`make_tft_labels.py` 產生中文）、`make_scenario_video.py`。原始專案在雲端硬碟 `claude\恐怖攻擊\公共場所AI監控通報`（本機手冊用它自己的 `手冊原始檔\build_handbook.py`），程式包是它的可攜擴充版：LINE 金鑰**只讀環境變數** `LINE_TOKEN`（原專案會讀「家中監控攝影機」的金鑰檔，不能放進程式包）。打包 `ai_guardian_starter_pack.zip`（保留資料夾層；排除 `yolov8n.pt`、`output/`、`logs/`、`events/`、`__pycache__`、`.venv`，`videos/` 只放說明檔）。不開鏡頭的測試：`system/test_rules.py`（47/47）；`make_demo_detections.py` → `batch_eval.py videos` 預期 6 件偵測到 5 件、誤報 1（桌旁走過）、重複 1、平均反應 2.18 秒；`--sweep WEAPON_SUSTAIN_SEC=0,0.6,1,2` 誤報 6/1/1/0，`--sweep WEAPON_CONF=0.25` 6/6 但誤報 2。韌體用 arduino-cli 編譯（需 Adafruit ST7735/GFX）。示意影片 `ai_guardian_scenario.mp4`（117 秒）、封面 `_poster.jpg`、TFT 預覽 `ai_guardian_tft_preview.png` 由 `make_scenario_video.py` 產生後複製到根目錄，改了規則或片段要同步手冊的文字稿時間。`analyze_video.py` 用真實影片測過（`影像辨識\.venv`），產生的截圖與影片會拍到人，測完要刪除。關卡 1～6 與監控牆會開鏡頭，未經同意不要執行；「手持」還沒用真剪刀實測，LINE 與警示盒硬體也還沒實測。
- AMB82-Mini 研習講義（115-12-02）：`amb82_iot_course_guide.html`，程式包 `amb82_course_starter/`（打包成 `amb82_course_starter_pack.zip`）。六支 .ino 都用 arduino-cli 實際編譯過：`"/c/Program Files/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe" compile --fqbn realtek:AmebaPro2:Ameba_AMB82-MINI <資料夾>`（開發板套件 realtek:AmebaPro2 4.1.0 已安裝，額外索引網址見講義；每支約 80 秒）。程式改寫自官方範例 repo `Ameba-AIoT/ameba-arduino-pro2`（分支 dev）。重點：TFT 要用內建 `AmebaILI9341`（在 SPI 函式庫裡），**Adafruit ST7735／BusIO 在這塊板子編譯不過**（`portOutputRegister` 未宣告）；Apps Script 部署權限必須選「任何人」，否則板子收到 302；LINE Notify 已停止服務，改用 Messaging API，圖片用雲端硬碟縮圖網址。沒有實機，所有硬體行為（上傳、串流、錄影、TFT、Telegram）都未實測，講義已標示。學生會在程式裡填 Token 與 Apps Script 網址，**填好的檔案不要 commit**。
- AMB82-Mini 第 2 天講義（116-01-18，AI 視覺辨識）：`amb82_ai_course_guide.html`（**加密頁**，原始檔、程式資料夾 `amb82_ai_starter/` 與 `amb82_ai_starter_pack.zip` 都放在 `_private/`，不進 repo；改完程式要重新打包 zip 再執行 `加密網頁.bat`，zip 會包進加密頁裡）。六支 .ino 都編譯過（01a 28%、01b 28%、02 41%、03 57%、06 28%）；`04_custom_model` 用 `CUSTOMIZED_YOLOV4TINY`，**必須加 `:06_LoadNNModelSource=sd` 才編得過**（Flash 模式會要求 .nb 放在草稿碼資料夾），SD 卡路徑寫死在程式庫 `SD_Model.cpp`：`sd:/NN_MDL/yolov4_tiny.nb`。板子只有 `LED_B`、`LED_G`；`ObjectClassList.h` 要和 .ino 同資料夾。電腦端 `pc_pose/`：`python test_pose_rules.py` 應為「通過 24 項，失敗 0 項」、`python pose_to_mqtt.py --selftest` 應送出 green_on、blink、close；講義的姿勢模擬器 JS 與 `pose_rules.py` 用 443 組數值比對過一致，改規則要兩邊一起改。**MediaPipe 要用沒翻過的畫面判斷，判斷完才 `cv2.flip` 顯示**，先翻會左右手對調。`cv2.imwrite` 遇中文路徑會安靜失敗，用 `imencode`＋`tofile`。Windows 終端機是 cp950，print 不要用 ✗ 之類的符號。姿態模型 `.task`（5.5 MB）不放進 zip，由 `download_model.py` 下載。沒有實機，所有板子行為與 MQTT 實際連線都未實測。
- 筆電＋USB 攝影機版（兩天 12 單元，AMB82 課程的改寫）：`laptop_cam_course_guide.html`（**公開頁，不加密**；網站根目錄放講義與 `laptop_cam_starter_pack.zip`；程式資料夾 `laptop_cam_starter/` 在 `_private/`，改完程式要重新打包 zip 再複製到根目錄）。講義的情境動畫播放器（13 個情境、`#sim=d2_03@6` 可直接跳到某秒）原始碼在講義最後的 `<script>`。程式包驗收：`python tools/make_demo_media.py` 後 `python tests/run_all_tests.py` 應為 OK 13（約 1～3 分鐘；`--with-train` 另測訓練，練習資料集 15 輪約 5 分鐘、mAP50 約 0.97）。所有單元都能 `--source demo/*.mp4` 取代攝影機，時間用影片時間所以結果可重現；**這台電腦有鏡頭，測試一律用示範影片，不要跑 `--source 0` 或 `tools/list_cameras.py`**。重點：QR 不可鏡像；MediaPipe 先判斷再鏡像；MQTT 預設連 `tools/mini_broker.py`（127.0.0.1），同一個 client id 重複連線會互踢（`mqtt_check.py` 已改成隨機 id，AMB82 第 2 天包也同步修正）；腳本文字不可用 cp950 印不出的字（`・`、`✗` 曾讓 `--help` 當掉）。模型（YOLO11n、YuNet、SFace、pose）與示範影片不進 zip，由 `tools/download_models.py`、`tools/make_demo_media.py` 產生。
- `ai_vision_course_guide.html` 的專題庫（11 題，第 09 題是 AI 守望）與下載包講義單元六內容要一致。
- 新增頁面時，要一起更新 `index.html` 的導覽連結和 `遠端網址備忘.txt`。
- 專案之前放在 `antigravity\stjweb`，舊文件裡如果還看到這個路徑，現在的位置是 Google 雲端硬碟的 `我的雲端硬碟\claude\stjweb`。使用者會在不同電腦上開這個專案，每台電腦的雲端硬碟磁碟代號不一樣（`H:`、`J:` 都出現過），以當次工作目錄為準，不要把磁碟代號寫死在腳本或文件裡。雲端硬碟上的 `du`、`find` 之類大量掃描很慢，盡量避免。
- 教學影片後製技能包（`teaching_video_pipeline_guide.html`＋`teaching_video_pipeline_master_pack.zip`，公開）：原始碼在 `_private/teaching_video_pipeline_pack/`（`_old/` 是 115-09-18 改版前的舊腳本，不進 zip）。改完要重新打包 zip，並把講義同步複製一份進 zip。驗收：`python tests/test_subtitles.py`（21 項）、`python tests/smoke_test.py`（用 Windows SAPI 中文語音自製假課程影片，跑裁切→辨識→字幕→壓製→上傳試跑，11 項，約 30 秒）。重點：字幕 SRT 已加片頭秒數、ASS 不加且在接片頭前燒；`condition_on_previous_text=False`＋逐字時間；OAuth 手動授權要用同一個 flow 物件（PKCE）。zip 不可含 `client_secrets.json`、`yt_token.json`、`config.json`（`D:\影片編輯` 的工作副本裡有真的憑證）。
