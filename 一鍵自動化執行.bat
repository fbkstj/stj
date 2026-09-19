@echo off
chcp 65001 >nul
title AI 課程影片自動化剪輯與發布系統

echo ======================================================================
echo 🎬 啟動 AI 課程影片全自動化剪輯、字幕重構與 YouTube 發布系統
echo ======================================================================
echo.

echo 🔍 [Step 1/3] 正在檢查 Python 環境與套件需求 (requirements.txt)...
python -m pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo ⚠️ 提示：環境檢查完成，準備執行主程式...
)

echo.
echo 🚀 [Step 2/3] 正在啟動影片全自動化處理流水線...
echo    ・FFmpeg 智能無聲段落過濾
echo    ・Faster-Whisper 語音轉字幕 (高職電機電子領域詞庫注入)
echo    ・OpenCC 台灣繁體用語對譯
echo    ・單行長句字幕重構 (15-25字/停留3-6秒)
echo    ・1080p 動態片頭合成與 FFmpeg 硬字幕陰影壓製
echo    ・YouTube API 批次發布與播放清單自動建置
echo.
python process_1150907_ai_course.py

echo.
echo ======================================================================
echo 🎉 處理完畢！請查看上方命令列輸出，或雙擊開啟 teaching_video_pipeline_guide.html 查看成果！
echo ======================================================================
echo.
pause
