@echo off
cd /d "%~dp0"
python -m PyInstaller --clean --onefile --noconsole --name "ZI-Ops" --icon="%~dp0ZI-Ops.ico" --version-file="%~dp0zi_ops_version.txt" --distpath="dist" zi_ops.py
if errorlevel 1 exit /b 1
