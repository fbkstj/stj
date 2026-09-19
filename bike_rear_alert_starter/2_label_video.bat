@echo off
pushd "%~dp0"
if "%~1"=="" (
  echo Drag a video file onto this .bat file.
  goto end
)
python label_events.py "%~1"
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
