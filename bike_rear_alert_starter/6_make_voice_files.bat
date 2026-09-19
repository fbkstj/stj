@echo off
pushd "%~dp0"
python make_voice_files.py
echo.
echo Done. Press any key to close.
pause >nul
popd
