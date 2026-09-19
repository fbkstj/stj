@echo off
rem Install Python packages (first time only)
pushd "%~dp0"
python -m pip install -r requirements.txt
echo.
echo Done. Press any key to close.
pause >nul
popd
