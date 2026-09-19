@echo off
rem Analyze the demo videos without starting the system
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
echo --- care_demo.mp4 (fall / inactive) ---
python -m modules.care.module demo\care_demo.mp4
echo --- door_demo.mp4 (visits) ---
python -m modules.camera.module demo\door_demo.mp4
echo.
echo Done. Press any key to close.
pause >nul
popd
