@echo off
setlocal
set "HERE=%~dp0"
py -3 -c "import PySide6, cryptography" >nul 2>&1 || py -3 -m pip install --user --quiet -r "%HERE%requirements-gui.txt"
start "" pyw -3 -E "%HERE%capmon_server_monitor.py" %*
