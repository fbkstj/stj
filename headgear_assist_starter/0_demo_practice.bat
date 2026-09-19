@echo off
pushd "%~dp0"
python make_demo_video.py
if errorlevel 1 goto end
python headgear_assist.py --video demo.mp4 --fake-sensor demo_sensor.csv --no-voice --window
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
