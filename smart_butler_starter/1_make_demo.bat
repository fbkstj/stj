@echo off
rem Make demo videos and fake routine data (no camera needed)
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
python demo\make_demo_media.py
python demo\make_routine_data.py
echo.
echo Done. Press any key to close.
pause >nul
popd
