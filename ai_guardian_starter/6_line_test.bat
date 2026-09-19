@echo off
pushd "%~dp0"
if not defined LINE_TOKEN (
  echo LINE_TOKEN is not set.
  echo Open cmd in this folder, run:  set LINE_TOKEN=your_channel_access_token
  echo then run:  python step6_line.py
  goto end
)
python step6_line.py
:end
echo.
echo Done. Press any key to close.
pause >nul
popd
