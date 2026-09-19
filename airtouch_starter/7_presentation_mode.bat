@echo off
pushd "%~dp0"
python airtouch.py --profile powerpoint
echo.
echo Done. Press any key to close.
pause >nul
popd
