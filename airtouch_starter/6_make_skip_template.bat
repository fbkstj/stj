@echo off
pushd "%~dp0"
python make_skip_template.py
echo.
echo Done. Press any key to close.
pause >nul
popd
