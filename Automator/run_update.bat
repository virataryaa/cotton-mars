@echo off
REM USDA MARS API - daily update (Task Scheduler: Program = cmd.exe, Arguments = /c "<this file>")
set "ROOT=C:\Users\virat.arya\ETG\SoftsDatabase - Documents\Database\Hardmine\Fundamental\Cotton\Cotton Mars"
set "PYTHON=C:\Users\virat.arya\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
set PYTHONUNBUFFERED=1
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
set "LOGFILE=%ROOT%\logs\update.log"
echo ===== %DATE% %TIME% ===== >> "%LOGFILE%"
cd /d "%ROOT%"
"%PYTHON%" "%ROOT%\Ingestion\run_update.py" >> "%LOGFILE%" 2>&1
exit /b %ERRORLEVEL%
