@echo off
pushd "%~dp0"
python tune_color.py
echo.
echo Done. Press any key to close.
pause >nul
popd
