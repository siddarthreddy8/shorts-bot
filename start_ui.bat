@echo off
cd /d "%~dp0"

echo Starting FastAPI backend on :8000 ...
start "Shorts Bot — API" cmd /k "uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo Starting React frontend on :5173 ...
cd src\ui
start "Shorts Bot — UI" cmd /k "npm run dev"

echo.
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo.
