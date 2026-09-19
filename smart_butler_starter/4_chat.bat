@echo off
rem Talk to the butler in this window (type q to quit)
pushd "%~dp0"
set PYTHONIOENCODING=utf-8
python -m modules.chat --demo
popd
