# רישום משימה מתוזמנת ב-Windows: ריצת הבוקר כל יום עבודה ב-07:30.
# מריצים פעם אחת, מ-PowerShell (קליק ימני -> Run with PowerShell):
#   .\register_task.ps1
# לשינוי השעה ערכו את $Time למטה והריצו שוב.

$Time = "07:30"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $ProjectDir "scripts\run_morning.bat"

$Action = New-ScheduledTaskAction -Execute $Bat
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday,Monday,Tuesday,Wednesday,Thursday -At $Time
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun

Register-ScheduledTask -TaskName "HearingAgent-Morning" `
    -Action $Action -Trigger $Trigger -Settings $Settings -Force

Write-Host "המשימה נרשמה: HearingAgent-Morning תרוץ בימים א'-ה' בשעה $Time"
