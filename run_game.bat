@echo off
cd /d "%~dp0"
if not exist .venv ( py -m venv .venv )
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
echo Starting Aware Rockets... it will open in your browser at http://localhost:8501
.venv\Scripts\python.exe -m streamlit run app.py
pause
