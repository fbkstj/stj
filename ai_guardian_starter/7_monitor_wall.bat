@echo off
pushd "%~dp0system"
rem Level 7: multi-camera wall + alarm box. Edit system\sources_config.py first. LINE is off here; to send LINE: set LINE_TOKEN, then run  python monitor.py
python monitor.py --no-line --serial auto
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
