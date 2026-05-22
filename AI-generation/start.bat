@echo off
echo Starting Clay Relief Pipeline...

:: Start backend (activate venv first)
start "Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate && uvicorn main:app --port 8001"

:: Give backend a moment
timeout /t 2 /nobreak >nul

:: Start frontend
start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:5173
echo.
echo Close the two terminal windows to stop.
pause