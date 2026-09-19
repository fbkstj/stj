@echo off
pushd "%~dp0"
python make_demo_video.py
if errorlevel 1 goto end
python rear_alert.py --video videos\demo.mp4 --window --no-serial
if errorlevel 1 goto end
python evaluate.py --truth videos\demo_truth.csv
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
