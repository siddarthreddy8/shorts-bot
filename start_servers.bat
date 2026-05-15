@echo off
start "Shorts Bot — API" cmd /k "cd /d D:\siddarth\youtube\shorts-bot && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
start "Shorts Bot — UI"  cmd /k "cd /d D:\siddarth\youtube\shorts-bot\src\ui && npm run dev"
