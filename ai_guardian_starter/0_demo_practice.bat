@echo off
pushd "%~dp0system"
rem No camera needed: rule tests, practice data, score table.
python test_rules.py
if errorlevel 1 goto end
python make_demo_detections.py
if errorlevel 1 goto end
python batch_eval.py videos --tag demo
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
