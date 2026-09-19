@echo off
pushd "%~dp0"
python make_report.py
echo.
echo Done. Press any key to close.
pause >nul
popd
