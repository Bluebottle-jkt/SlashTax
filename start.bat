@echo off
echo ========================================
echo Starting SlashTax Application
echo ========================================
echo.

:: Start Backend
echo Starting Backend Server...
start "SlashTax Backend" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

:: Wait a bit for backend to start
timeout /t 3 /nobreak >nul

:: Start Frontend
echo Starting Frontend Server...
start "SlashTax Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo Servers starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Make sure Neo4j is running before using the app!
echo.

:: Open browser
timeout /t 5 /nobreak >nul
start http://localhost:3000
