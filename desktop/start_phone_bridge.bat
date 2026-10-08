@echo off
cd /d "%~dp0"
python phone_bridge.py --host 0.0.0.0 --port 8765
pause
