@echo off
pushd "%~dp0"
python evaluate_gestures.py
echo.
echo Done. Press any key to close.
pause >nul
popd
