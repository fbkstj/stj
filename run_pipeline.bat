@echo off
title AI Video Pipeline Execution Script

echo ======================================================================
echo AI Video Pipeline Automated Processing & YouTube Publishing
echo ======================================================================
echo.

echo Checking requirements...
python -m pip install -q -r requirements.txt

echo.
echo Launching main processing script...
python process_1150907_ai_course.py

echo.
echo ======================================================================
echo Done! Press any key to exit.
echo ======================================================================
pause
