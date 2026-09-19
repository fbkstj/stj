@echo off
pushd "%~dp0"
rem Level 3: held object (use scissors). Press q to quit.
rem Double-click: camera 0.  Drag a video file onto this .bat: use that video.
if "%~1"=="" (python step3_weapon.py) else (python step3_weapon.py "%~1")
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
