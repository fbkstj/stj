@echo off
pushd "%~dp0"
python test_voice_logic.py
echo.
echo Done. Press any key to close.
pause >nul
popd
