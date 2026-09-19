@echo off
cd /d "%~dp0"
echo Adding changes to Git...
git add .
echo Committing changes...
git commit -m "Update site"
echo Pushing to GitHub...
git push origin main --force
echo Done!
pause
