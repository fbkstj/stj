@echo off
rem Start the whole system in demo mode for 3 minutes (demo videos, Discord dry run)
rem Dashboard: http://127.0.0.1:8765   Press F9 = SOS, q = quit
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
start "" http://127.0.0.1:8765
python main.py --demo --duration 180
echo.
echo Done. Press any key to close.
pause >nul
popd
