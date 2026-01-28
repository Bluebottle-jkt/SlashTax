@echo off
echo ========================================
echo SlashTax Setup Script for Windows
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org
    exit /b 1
)

echo [1/5] Setting up Backend...
cd backend

:: Create virtual environment
if not exist venv (
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate

:: Install dependencies
echo Installing Python dependencies...
pip install -e . --quiet

:: Create .env if not exists
if not exist .env (
    copy .env.example .env
    echo Created .env file - please configure your API keys
)

cd ..

echo [2/5] Setting up Frontend...
cd frontend

:: Install npm dependencies
echo Installing npm dependencies...
call npm install --silent

cd ..

echo [3/5] Creating data directories...
if not exist data\uploads mkdir data\uploads
if not exist data\faces mkdir data\faces

echo [4/5] Setup Complete!
echo.
echo ========================================
echo IMPORTANT: Before running the app:
echo ========================================
echo.
echo 1. Start Neo4j Desktop or run:
echo    docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5.15.0
echo.
echo 2. Configure backend\.env with:
echo    - NEO4J_PASSWORD
echo    - ANTHROPIC_API_KEY
echo    - OPENAI_API_KEY
echo.
echo 3. Start the backend:
echo    cd backend
echo    venv\Scripts\activate
echo    uvicorn app.main:app --reload
echo.
echo 4. Start the frontend (new terminal):
echo    cd frontend
echo    npm run dev
echo.
echo 5. Open http://localhost:3000
echo ========================================

pause
