@echo off
pushd "%~dp0"
set /p TAG=Tag (name_distance_light): 
python collect_samples.py --tag "%TAG%"
echo.
echo Done. Press any key to close.
pause >nul
popd
