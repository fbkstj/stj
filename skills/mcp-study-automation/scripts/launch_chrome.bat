@echo off
title AI Chrome Launcher (Port 9222)
echo ========================================================
echo   啟動 AI 無障礙伴讀 Chrome (除錯埠 Port 9222)...
echo ========================================================
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\AI_Profile" "https://elearning.taipei/mpage/"
echo [OK] Chrome 視窗已啟動！請登入並點開您的研習課程。
pause
