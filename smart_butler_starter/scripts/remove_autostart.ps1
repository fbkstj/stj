# 移除開機自動啟動（刪除工作排程器中的 SmartButler 工作）
# 執行方式：powershell -ExecutionPolicy Bypass -File scripts\remove_autostart.ps1

$TaskName = "SmartButler"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已移除排程工作 $TaskName"
} else {
    Write-Host "沒有找到排程工作 $TaskName，不需要移除"
}
