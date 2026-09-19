@echo off
rem Send info / warn / urgent test messages (dry run unless discord.dry_run is false)
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
python -m core.config
python -m core.notify --test
echo.
echo Done. Press any key to close.
pause >nul
popd
