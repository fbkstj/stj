@echo off
rem Daily summary of the demo data, and routine check on 10 days of fake data
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
python -m modules.daily --now --demo --print-only
echo.
python -m modules.routine --check --db demo\routine_demo.db --all
echo.
echo Done. Press any key to close.
pause >nul
popd
