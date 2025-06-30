@echo off
echo Starting Recruitment Similarity & Ranking System...
echo.

echo 1. Starting Backend Server...
cd backend
start "Backend Server" cmd /k "py -m uvicorn main:app --reload"
cd ..

echo 2. Opening Frontend...
timeout /t 3 /nobreak >nul
start frontend/login.html

echo.
echo Application started!
echo Backend: http://127.0.0.1:8000
echo Frontend: login.html (opened in browser)
echo.
echo Press any key to exit...
pause >nul 