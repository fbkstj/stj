@echo off
pushd "%~dp0"
if "%~1"=="" (
  echo Drag a video file onto this .bat file.
  goto end
)
python rear_alert.py --video "%~1" --window --save --no-serial
if errorlevel 1 goto end
if exist "%~dpn1_truth.csv" python evaluate.py --truth "%~dpn1_truth.csv"
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
