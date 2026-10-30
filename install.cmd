@echo off
rem Amer installer for Windows - double-click this file, or run: install.cmd [--only claude,omp,antigravity] [--uninstall]
cd /d "%~dp0"
where py >nul 2>nul && (py -3 install.py %* & goto :done)
where python >nul 2>nul && (python install.py %* & goto :done)
echo Python 3 was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run this again.
:done
echo.
pause
