@echo off
REM Build standalone gsr.exe from gsr_main.py for Windows
pyinstaller --onefile --name gsr gsr_main.py