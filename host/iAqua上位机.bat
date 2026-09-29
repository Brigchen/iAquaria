@echo off
rem ============================================
rem iAqua PC host launcher
rem Usage:
rem   double-click        -> connect ws://iaqua.local/ws  (device on home LAN)
rem   with argument       -> iAqua_host.bat ws://192.168.4.1/ws  (device AP mode)
rem ============================================
set URL=%1
if "%URL%"=="" set URL=ws://iaqua.local/ws
cd /d "%~dp0"
echo iAqua host connecting to %URL% ...
C:\Users\brigc\anaconda3\envs\iaqua-host\python.exe iaqua_host.py %URL%
if errorlevel 1 (
  echo.
  echo iAqua host exited with an error.
  pause
)
