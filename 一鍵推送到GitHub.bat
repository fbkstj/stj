@echo off
chcp 65001 > nul
title 推送網站至 GitHub Pages
echo ========================================================
echo   正在將網站最新進度推送到 GitHub (fbkstj/www)...
echo ========================================================
echo.
cd /d "%~dp0"
git add .
git commit -m "Auto Update: %date% %time%"
git push -u origin main --force
echo.
echo ========================================================
echo   更新完成！請開啟 https://fbkstj.github.io/www/ 查看！
echo ========================================================
pause
