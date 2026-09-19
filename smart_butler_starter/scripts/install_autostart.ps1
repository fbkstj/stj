# 安裝開機自動啟動（L14）
# 會在 Windows「工作排程器」建立一個名為 SmartButler 的工作：
#   觸發：目前使用者登入時
#   動作：在專案資料夾執行 python main.py（正式模式）
#   設定：當掉時每 1 分鐘重試，最多 3 次；使用電池時也照常執行
# 執行方式（不需要系統管理員）：
#   powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
# 移除：scripts\remove_autostart.ps1

$ErrorActionPreference = "Stop"
$TaskName = "SmartButler"
$Project = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Host "找不到 python，請先安裝 Python 並勾選 Add python.exe to PATH"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument "main.py" -WorkingDirectory $Project
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 3 -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "智慧管家系統：登入時自動啟動 main.py" -Force | Out-Null

Write-Host "已建立排程工作 $TaskName"
Write-Host "  程式：$Python main.py"
Write-Host "  資料夾：$Project"
Write-Host "重新登入或重開機後就會自動啟動。要移除請執行 scripts\remove_autostart.ps1"
