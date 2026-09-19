@echo off
pushd "%~dp0"
python evaluate_trials.py
echo.
echo Done. Press any key to close.
pause >nul
popd
