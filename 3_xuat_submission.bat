@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
%PY% policyassist.py batch
echo.
echo Kiem tra doc lap file nop:
%PY% validate_submission.py
echo.
echo Ket qua: outputs\submission.csv
pause
