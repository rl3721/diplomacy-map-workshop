@echo off
cd /d "%~dp0"
python -m mapgen.app
if errorlevel 1 pause
