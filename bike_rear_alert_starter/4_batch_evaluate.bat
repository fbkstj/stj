@echo off
pushd "%~dp0"
python batch_run.py videos
echo.
echo Done. Press any key to close.
pause >nul
popd
