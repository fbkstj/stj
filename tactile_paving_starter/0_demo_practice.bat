@echo off
pushd "%~dp0"
python make_demo_video.py
if errorlevel 1 goto end
python paving_monitor.py --config demo_config.json
if errorlevel 1 goto end
python evaluate.py --truth demo_ground_truth.csv --state output_demo/state_log.csv --min-event 5
python make_report.py --dir output_demo
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
