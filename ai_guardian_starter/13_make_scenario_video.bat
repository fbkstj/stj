@echo off
pushd "%~dp0system"
rem Teacher: rebuild output\scenario_demo.mp4 (needs ffmpeg).
python make_scenario_video.py
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
