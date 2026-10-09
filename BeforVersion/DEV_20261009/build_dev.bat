@echo off
cd /d "%~dp0"
python -m PyInstaller --clean --onefile --noconsole --name "ZI-Ops DEV" --icon="%~dp0ZI-Ops.ico" --version-file="%~dp0zi_ops_dev_version.txt" --workpath="build_dev" --specpath="dev_spec" zi_ops_dev.py
pause
