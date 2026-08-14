@echo off
echo ============================================
echo   OpenClaw Cleanup Script (Run as Admin)
echo ============================================
echo.

echo [1/6] Stopping OpenClawGateway service...
sc.exe stop OpenClawGateway >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/6] Removing OpenClawGateway service...
sc.exe delete OpenClawGateway >nul 2>&1
timeout /t 2 /nobreak >nul

echo [3/6] Disabling conflicting scheduled tasks...
schtasks /End /TN "OpenClaw Gateway" >nul 2>&1
schtasks /Change /TN "OpenClaw Gateway" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw Health Check" >nul 2>&1
schtasks /Change /TN "OpenClaw Health Check" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw Stack - Flask Handler" >nul 2>&1
schtasks /Change /TN "OpenClaw Stack - Flask Handler" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw Stack - Jarvis AGI" >nul 2>&1
schtasks /Change /TN "OpenClaw Stack - Jarvis AGI" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw Stack - OpenClaw Gateway" >nul 2>&1
schtasks /Change /TN "OpenClaw Stack - OpenClaw Gateway" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw Storage Cleanup" >nul 2>&1
schtasks /Change /TN "OpenClaw Storage Cleanup" /DISABLE >nul 2>&1
schtasks /End /TN "OpenClaw-Healthcheck" >nul 2>&1
schtasks /Change /TN "OpenClaw-Healthcheck" /DISABLE >nul 2>&1
schtasks /End /TN "EnterpriseRAG" >nul 2>&1
schtasks /Change /TN "EnterpriseRAG" /DISABLE >nul 2>&1
timeout /t 2 /nobreak >nul

echo [4/6] Killing stale node processes on port 18789...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :18789 ^| findstr LISTENING') do (
    echo Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [5/6] Clearing crash-loop state...
if exist "C:\Users\user\.openclaw\logs\stability" (
    del /q "C:\Users\user\.openclaw\logs\stability\*" >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [6/6] Starting OpenClaw gateway cleanly...
start "OpenClaw Gateway" /B C:\Users\user\.openclaw\gateway.cmd
timeout /t 15 /nobreak >nul

echo.
echo ============================================
echo   Cleanup complete
echo ============================================
echo   Check health: curl http://localhost:18789/health
echo   Check channels: openclaw channels status
echo.
pause
