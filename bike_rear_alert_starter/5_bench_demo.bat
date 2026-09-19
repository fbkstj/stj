@echo off
pushd "%~dp0"
python rear_alert.py --camera --window
echo.
echo Done. Press any key to close.
pause >nul
popd
