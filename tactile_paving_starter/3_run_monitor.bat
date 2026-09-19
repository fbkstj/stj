@echo off
pushd "%~dp0"
python paving_monitor.py
echo.
echo Done. Press any key to close.
pause >nul
popd
