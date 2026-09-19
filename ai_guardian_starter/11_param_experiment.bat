@echo off
pushd "%~dp0system"
rem Compare thresholds on the same data (threat_rules.py is not changed).
python batch_eval.py videos --sweep WEAPON_CONF=0.25,0.35,0.5
python batch_eval.py videos --sweep WEAPON_SUSTAIN_SEC=0,0.6,1,2
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
