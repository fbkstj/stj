@echo off
rem Run all automatic tests (L1-L14, T16)
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
python tests\run_all_tests.py
echo.
echo Done. Press any key to close.
pause >nul
popd
