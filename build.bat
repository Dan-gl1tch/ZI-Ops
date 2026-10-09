@echo off
cd /d "%~dp0"
python -m pip install customtkinter==6.0.0 websocket-client pyinstaller
if errorlevel 1 exit /b 1
python -m PyInstaller --clean --onefile --noconsole --collect-all customtkinter --add-data="ZI-Ops.ico;." --name "ZI-Ops" --icon="%~dp0ZI-Ops.ico" --version-file="%~dp0zi_ops_version.txt" --distpath="dist" zi_ops.py
if errorlevel 1 exit /b 1
