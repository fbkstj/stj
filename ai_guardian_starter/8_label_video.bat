@echo off
pushd "%~dp0system"
rem Drag a drill video here: press 1-4 at the start AND end of each event.
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
