@echo off
pushd "%~dp0"
rem Level 5: snapshot, log, 5 s cancel window. c = cancel, q = quit.
rem Double-click: camera 0.  Drag a video file onto this .bat: use that video.
if "%~1"=="" (python step5_alert.py) else (python step5_alert.py "%~1")
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
