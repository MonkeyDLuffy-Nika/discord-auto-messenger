@echo off
cd /d "%~dp0"
title Discord Auto-Messenger
cls
echo Starting Discord Auto-Messenger...

python -c "import customtkinter, requests, cryptography" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [!] Installing required dependencies...
    python -m pip install customtkinter requests cryptography
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo [!] Error running main.py. Checking dependencies...
    python -m pip install customtkinter requests cryptography
    echo.
    echo [*] Retrying launch...
    python main.py
    if %errorlevel% neq 0 (
        echo.
        echo [!] Launch failed. Press any key to exit.
        pause
    )
)
