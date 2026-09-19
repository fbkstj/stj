# 進度紀錄（PROGRESS.md）

這是老師提供的**參考程式包**：L0～L15 都已經有一個可以執行的版本。
你們的組別可以：
- 照手冊一關一關自己做，卡住時對照這裡的寫法；或
- 以這個程式包為起點，把自己的 Aina 功能搬進來、改成你們的版本。

每完成一項，就在下表打勾，並寫下「做了什麼決定」「遇到什麼問題」。

## 關卡進度

| 關卡 | 內容 | 參考程式 | 我們的狀態 |
|---|---|---|---|
| L0 | 專案骨架與規則 | 資料夾、`docs/專案規則.md`、本檔案 | [ ] |
| L1 | 設定中心與 .env | `core/config.py`、`config/settings.yaml` | [ ] |
| L2 | 事件匯流排與紀錄 | `core/events.py`、`core/store.py` | [ ] |
| L3 | Discord 通報分級 | `core/notify.py` | [ ] |
| L4 | 主程式與模組管理 | `main.py`、`core/module.py`、`core/supervisor.py` | [ ] |
| L5 | 長照監護 | `modules/care/` | [ ] |
| L6 | AI 對話與家電 | `modules/chat/` | [ ] |
| L7 | 留言板 | `modules/board/` | [ ] |
| L8 | 智慧監視器 | `modules/camera/` | [ ] |
| L9 | 本機管理介面 | `web/` | [ ] |
| L10 | 用藥提醒 | `modules/meds/` | [ ] |
| L11 | 每日平安回報 | `modules/daily/` | [ ] |
| L12 | 一鍵求救 | `modules/sos/` | [ ] |
| L13 | 作息異常偵測 | `modules/routine/`、`demo/make_routine_data.py` | [ ] |
| L14 | 系統穩定 | `core/health.py`、`scripts/*.ps1` | [ ] |
| L15 | 整合驗收 | `tests/`、手冊 08 驗收表 | [ ] |

## 已做的決定

- 示範模式（`--demo`）的資料放在 `data/demo/`，和正式資料分開；時間參數由 `config/demo_overrides.yaml` 縮短。
- 參考程式的人物偵測是「背景相減」，只適用程式畫的示範影片；接真實攝影機要換成 MediaPipe 或 YOLO（見 README）。

## 已知問題

- Discord「已處理」用管理介面按鈕或在留言板頻道輸入「已處理 編號」，還沒有做成 Discord 訊息上的按鈕。
- 讀取 Discord 留言（Bot）、真實 Webhook、Windows 語音、開機自動啟動腳本都還沒有在實機上測過。
