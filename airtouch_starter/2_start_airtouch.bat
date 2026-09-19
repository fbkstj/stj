@echo off
pushd "%~dp0"
python airtouch.py
echo.
echo Done. Press any key to close.
pause >nul
popd
