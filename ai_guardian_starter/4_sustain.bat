@echo off
pushd "%~dp0"
rem Level 4: sustained alarm. Press q to quit.
rem Double-click: camera 0.  Drag a video file onto this .bat: use that video.
if "%~1"=="" (python step4_sustain.py) else (python step4_sustain.py "%~1")
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
