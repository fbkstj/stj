@echo off
pushd "%~dp0system"
rem Drag a drill video here: YOLO analysis, annotated video, snapshots, score.
if "%~1"=="" (
  echo Drag a video file onto this .bat file.
  goto end
)
python analyze_video.py "%~1" --show --save
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
