@echo off
pushd "%~dp0system"
rem Test the ESP32 alarm box: lights, TFT, button.
python test_alarm.py %1
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
