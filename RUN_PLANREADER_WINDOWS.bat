@echo off
title Premier Brushworks Plan Reader and 3D Take-off
cd /d "%~dp0"

if /I "%~1"=="benchmark" goto local_benchmark

echo.
echo Premier Brushworks Plan Reader and 3D Take-off
echo =================================================
echo.
echo Installing or updating requirements...
py -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 python -m pip install -r requirements.txt

echo.
echo Starting PlanReader v1.5.1...
py -m streamlit run pb_planreader_v133_app.py
if %ERRORLEVEL% NEQ 0 python -m streamlit run pb_planreader_v133_app.py
pause
exit /b

:local_benchmark
python -m tools.run_frozen120_owner_benchmark %*
exit /b %ERRORLEVEL%
