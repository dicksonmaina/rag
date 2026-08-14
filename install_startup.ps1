# Install-EnterpriseRAG-Startup.ps1
# Run this as Administrator to create a system-wide scheduled task
# that starts Enterprise RAG + OpenClaw on boot

$taskName = "EnterpriseRAG"
$action = New-ScheduledTaskAction -Execute "C:\Users\user\RAG\start_enterprise.bat" -WorkingDirectory "C:\Users\user\RAG"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -RunLevel Highest -LogonType S4U

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Start Enterprise RAG + OpenClaw on boot" -Force

Write-Host "Scheduled task '$taskName' created successfully."
Write-Host "To remove it later, run: schtasks /Delete /TN '$taskName' /F"
