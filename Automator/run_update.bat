@echo off
REM USDA MARS API - daily update: ingest, then push Database to GitHub
cd /d "%~dp0.."
if not exist logs mkdir logs
python Ingestion\mars_ingest.py >> logs\update.log 2>&1
if errorlevel 1 (echo ingest failed >> logs\update.log & exit /b 1)
git add Database >> logs\update.log 2>&1
git diff --cached --quiet && (echo no change >> logs\update.log & exit /b 0)
git commit -m "Daily MARS update %date%" >> logs\update.log 2>&1
git push origin main >> logs\update.log 2>&1
