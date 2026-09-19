@echo off
pushd "%~dp0"
rem Level 1: camera view. Press q to quit.
rem Double-click: camera 0.  Drag a video file onto this .bat: use that video.
if "%~1"=="" (python step1_camera.py) else (python step1_camera.py "%~1")
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
