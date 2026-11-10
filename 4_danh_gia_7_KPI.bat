@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
%PY% policyassist.py eval
echo.
echo Bao cao: outputs\eval_report.md  -  outputs\kpi_table.csv  -  outputs\error_table.csv
pause
