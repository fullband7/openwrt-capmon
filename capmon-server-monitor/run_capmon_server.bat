@echo off
setlocal
set "HERE=%~dp0"
if exist "%HERE%certs\server.key" goto run
py -3 -c "import cryptography" >nul 2>&1 && goto run
py -3 -m pip install --user --quiet -r "%HERE%requirements.txt"
:run
py -3 "%HERE%capmon_server.py" %*
pause
