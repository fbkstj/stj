@echo off
pushd "%~dp0"
python headgear_assist.py
echo.
echo Done. Press any key to close.
pause >nul
popd
