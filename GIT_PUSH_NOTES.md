# Git Push 背景推送失敗原因與解決方案紀錄

## 📌 問題現象
在 AI 助理（Antigravity Agent）環境中，若直接執行 `git push origin main` 或試圖從背景呼叫 `.bat` 批次檔，會出現以下狀況：
1. 本機 `git add` 與 `git commit` 可以正常成功。
2. 但 `git push` 卻卡在背景執行中、無限等待或顯示 Timeout / Canceled。
3. 使用者桌面上並未看到憑證登入視窗或 CMD 視窗彈出。

---

## 🔍 根本原因分析
1. **Windows Session 0 隔離機制 (Session 0 Isolation)**：
   - AI 助理運作於 Windows 背景服務與非互動式 Shell（Session 0）。
   - Windows 作業系統為防範安全風險，禁止 Session 0 的程序直接在使用者互動桌面（Session 1）上繪製 GUI 介面或跳出彈窗。

2. **Git Credential Manager (GCM) 登入視窗被擋**：
   - 當 Git 使用 HTTPS (`https://github.com/fbkstj/www.git`) 進行 `git push` 時，Git 憑證管理工具 (Git Credential Manager) 會試圖彈出 GUI 視窗請求帳號密碼驗證或 OAuth 授權。
   - 由於在 Session 0 背景環境中無法顯示 GUI 視窗，GCM 陷入等待使用者輸入的狀態，導致 Git 命令卡死。

---

## 🛠️ 最佳解決方案
當 AI 完成網頁代碼修改與 `git commit` 存檔後：
1. **最可靠方式**：使用者至本機資料夾雙擊執行 **`一鍵推送到GitHub.bat`** 或 **`deploy.bat`**。
2. **原因**：由使用者桌面（Session 1）直接點擊執行的腳本能正常喚起 GCM 驗證視窗與讀取本機憑證，可於 1 秒內順利推送至 GitHub Pages。
