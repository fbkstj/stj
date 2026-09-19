@echo off
pushd "%~dp0"
python make_demo_samples.py
python evaluate_gestures.py data\demo_samples.csv
python test_voice_commands.py
python test_trigger.py
python test_profiles.py
echo.
echo Done. Press any key to close.
pause >nul
popd
