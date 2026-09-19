@echo off
pushd "%~dp0system"
rem Score table for every video in videos\ that has a _truth.csv.
python batch_eval.py videos
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
