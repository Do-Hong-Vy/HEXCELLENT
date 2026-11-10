@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
echo [PolicyAssist AI] Cai dat thu vien tu requirements.txt ...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
echo.
echo Xong. Chay 2_mo_giao_dien.bat de mo giao dien.
pause
