@echo off
pushd "%~dp0"
python test_lights.py
echo.
echo Done. Press any key to close.
pause >nul
popd
