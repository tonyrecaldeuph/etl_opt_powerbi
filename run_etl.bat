@echo off
REM Entrypoint del ETL para el Programador de tareas de Windows
cd /d C:\dwh\etl
call .venv\Scripts\activate.bat
set PYTHONPATH=src
python -m etl.runner >> C:\dwh\logs\etl_%date:~-4%%date:~3,2%%date:~0,2%.log 2>&1
