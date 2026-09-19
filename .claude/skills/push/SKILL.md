---
name: push
description: 把 stjweb 的修改 commit 並推送到 GitHub（fbkstj/www，GitHub Pages 正式站）。使用者說「推上 GitHub」「推送」「上傳網站」「push」「部署」或打 /push 時使用。會先檢查機密檔與大型檔，再用不會卡住的方式推送，不使用 --force。
---

# 推送 stjweb 到 GitHub

正式站 https://fbkstj.github.io/www/ 由 repo `fbkstj/www` 的 `main` 分支自動部署。網站完全公開，推上去就等於發布。

## 1. 看有哪些修改

```bash
git status --short
git log origin/main..HEAD --oneline   # 已 commit 但還沒推的
```

沒有任何修改也沒有待推的 commit → 告訴使用者「沒有東西要推」，結束。

## 2. 推送前檢查（任一項不過就停下來問使用者）

- **機密檔**：`client_secrets.json`、`yt_token.json`，或任何含 token、password、API key 的檔案，不可出現在要 commit 的清單裡。
- **zip 內容**：有新增或修改的 `.zip`，用 `unzip -l <檔名>` 檢查，裡面不可有上面的機密檔（`.gitignore` 管不到 zip 裡面）。
- **大型檔**：單檔超過 10 MB（影片、壓縮包、`*.pt` 模型）先問使用者。`.git` 已經約 1.3 GB，影片應該放 YouTube 或雲端硬碟。
- **學生個資**：身分證、電話、完整座號姓名對照等不可公開。
- **加密頁面**：`app_inventor_answers.html`、`mcp_course_automation_guide.html`、`amb82_iot_course_guide.html`、`amb82_ai_course_guide.html` 若在修改清單中，要確認是加密後的版本（`grep -c staticrypt` 大於 0，且找不到原文，例如 `grep -c "App Inventor"` 為 0）。`_private/` 底下任何檔案都不可 commit。
- **不相關的檔案**：一次性腳本、暫存檔、測試產物，確認使用者是否真的要推。

## 3. Commit

- 只 `git add` 這次相關的檔案，**不要用 `git add .`**。
- 新增頁面時，確認 `index.html` 導覽連結和 `遠端網址備忘.txt` 也一起更新了（見 CLAUDE.md）。
- Commit 訊息沿用既有風格：英文、祈使句開頭的標題（例：`Add ...`、`Fix ...`、`Update ...`），需要時空一行寫條列說明，最後加上 Co-Authored-By 那行。

## 4. 推送

```bash
GCM_INTERACTIVE=never GIT_TERMINAL_PROMPT=0 timeout 90 git push origin main
```

這樣 Git Credential Manager 不會在背景等登入視窗而卡死，已存好的憑證可以直接用。

- **被拒絕（non-fast-forward）**：先 `git pull --rebase origin main`，解決衝突後再推。**絕對不要 `--force`**。
- **認證失敗或逾時（exit 124）**：請使用者自己開終端機，在 stjweb 資料夾執行 `git push origin main`（commit 已經做好了）。不要叫使用者雙擊 `一鍵推送到GitHub.bat` / `deploy.bat`，這兩個會 `git add .` 並 `--force` 推送。

## 5. 確認

```bash
git status -sb                    # 應該顯示與 origin/main 同步
git log origin/main -1 --oneline
```

回報使用者：推了哪些 commit、改了哪些頁面，附上正式站網址（GitHub Pages 通常 1～2 分鐘後更新）。
