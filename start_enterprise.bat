@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   Enterprise RAG + OpenClaw Startup
echo ============================================
echo.

:: Check if Ollama is already running
netstat -ano | findstr ":11434.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [1/3] Ollama already running on port 11434, skipping.
) else (
    echo [1/3] Starting Ollama...
    start "Ollama" /B ollama serve
    timeout /t 3 /nobreak >nul
)

:: Check if RAG server is already running
netstat -ano | findstr ":9000.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [2/3] RAG Server already running on port 9000, skipping.
) else (
    echo [2/3] Starting Enterprise RAG Server...
    start "RAG Server" /B python "C:\Users\user\RAG\scripts\enterprise_rag.py" serve --port 9000
    timeout /t 4 /nobreak >nul
)

:: Check if OpenClaw gateway is already running
netstat -ano | findstr ":18789.*LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [3/3] OpenClaw Gateway already running on port 18789, skipping.
) else (
    echo [3/3] Starting OpenClaw Gateway...
    start "OpenClaw Gateway" /B "C:\Users\user\.openclaw\gateway.cmd"
    timeout /t 5 /nobreak >nul
)

echo.
echo ============================================
echo   Startup check complete
echo ============================================
echo   RAG Server:  http://localhost:9000
echo   RAG Docs:    http://localhost:9000/docs
echo   OpenClaw:    http://localhost:18789
echo.
timeout /t 2 /nobreak >nul
