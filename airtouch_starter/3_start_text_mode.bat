@echo off
pushd "%~dp0"
python airtouch.py --text
echo.
echo Done. Press any key to close.
pause >nul
popd
