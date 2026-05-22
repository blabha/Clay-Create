@echo off
echo Starting Clay Relief Pipeline...

:: Start backend
start "Backend" cmd /k "cd /d "%~dp0backend" && uvicorn main:app --reload --port 8000"

:: Give backend a moment
timeout /t 2 /nobreak >nul

:: Start frontend
start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Close the two terminal windows to stop.
pause
