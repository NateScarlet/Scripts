$RegPath = "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
$CurrentTime = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
$EndTime = [DateTime]::UtcNow.AddYears(100).ToString("yyyy-MM-ddTHH:mm:ssZ")

try {
    # 设置注册表值
    New-ItemProperty -Path $RegPath -Name "PauseFeatureUpdatesStartTime" -Value $CurrentTime -PropertyType String -Force -ErrorAction Stop | Out-Null
    New-ItemProperty -Path $RegPath -Name "PauseFeatureUpdatesEndTime" -Value $EndTime -PropertyType String -Force -ErrorAction Stop | Out-Null
    New-ItemProperty -Path $RegPath -Name "PauseQualityUpdatesStartTime" -Value $CurrentTime -PropertyType String -Force -ErrorAction Stop | Out-Null
    New-ItemProperty -Path $RegPath -Name "PauseQualityUpdatesEndTime" -Value $EndTime -PropertyType String -Force -ErrorAction Stop | Out-Null
    New-ItemProperty -Path $RegPath -Name "PauseUpdatesStartTime" -Value $CurrentTime -PropertyType String -Force -ErrorAction Stop | Out-Null
    New-ItemProperty -Path $RegPath -Name "PauseUpdatesExpiryTime" -Value $EndTime -PropertyType String -Force -ErrorAction Stop | Out-Null

    Write-Host "`n成功设置更新暂停 Windows 更新（设置中可手动恢复更新）：" -ForegroundColor Green
    Write-Host "开始时间: $CurrentTime"
    Write-Host "结束时间: $EndTime"

    Start-Process ms-settings:windowsupdate
}

catch [System.UnauthorizedAccessException] {
    Write-Host "`n错误：访问被拒绝" -ForegroundColor Red
    Write-Host "可能原因:"
    Write-Host "1. 未使用管理员权限运行" -ForegroundColor Yellow
    Write-Host "2. 系统策略限制注册表修改"
    Write-Host "3. 防病毒软件阻止操作`n"
    Write-Host "解决方案:"
    Write-Host "• 右键单击PowerShell图标，选择'以管理员身份运行'"
    Write-Host "• 检查组策略设置 (gpedit.msc)"
    Write-Host "• 临时禁用防病毒软件后重试"
    exit 1
}
catch {
    Write-Host "`n未知错误: $_" -ForegroundColor Red
    exit 2
}
