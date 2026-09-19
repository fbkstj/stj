@echo off
pushd "%~dp0"
python make_scenario_video.py
echo.
echo Done. Press any key to close.
pause >nul
popd
