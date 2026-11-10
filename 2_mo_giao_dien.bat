@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
echo [PolicyAssist AI] Dang mo giao dien tai http://localhost:8501 (dong cua so nay de dung)
%PY% policyassist.py ui
pause
