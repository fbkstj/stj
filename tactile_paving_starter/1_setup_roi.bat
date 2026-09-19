@echo off
pushd "%~dp0"
python setup_roi.py
echo.
echo Done. Press any key to close.
pause >nul
popd
