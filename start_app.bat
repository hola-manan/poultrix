@echo off
cd /d "%~dp0"

echo Starting API Server in a new window...
start "API Server" cmd /k ".\.venv\Scripts\activate && set PYTHONPATH=%cd%\src && uvicorn jeevn.api.app:app --reload --port 8000"

:: Wait for the API to bind before launching the UI
timeout /t 5 /nobreak > nul

echo Starting Streamlit UI in a new window...
start "Streamlit UI" cmd /k ".\.venv\Scripts\activate && set PYTHONPATH=%cd%\src && streamlit run src\jeevn\ui\app.py"

echo Services have been launched successfully! You can close this window.
