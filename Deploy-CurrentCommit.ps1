#Requires -Version 7.0
$ErrorActionPreference = "Stop"

# 目标脚本路径（本地应用程序数据目录）
$targetDir = Join-Path $env:LOCALAPPDATA "Scripts"

# 检查未提交文件
$uncommitted = git status --porcelain | Where-Object { $_ -notmatch "^.. Deploy-CurrentCommit\.ps1$" } # 忽略自身方便测试
if ($uncommitted) {
    Write-Host "❌ 存在未提交的修改，请先提交或暂存后再部署：" -ForegroundColor Red
    Write-Host $uncommitted
    exit 1
}

$currentHead = git rev-parse HEAD
# 如果目标目录不存在，创建并初始化工作树
if (-not (Test-Path $targetDir -PathType Container)) {
    # 使用 git worktree 创建新工作树
    git worktree add --detach $targetDir $currentHead
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 创建工作树失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "🌱 创建新工作树: $targetDir"
}
else {
    # 直接更新现有工作树到当前HEAD
    $previousHead = git -C $targetDir rev-parse HEAD
    if ($previousHead -eq $currentHead) {
        Write-Host "⏩ 工作树已经位于 $($currentHead.Substring(0,7))，无需更新"
    }
    else {
        git -C $targetDir checkout --detach $currentHead
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 目标目录更新失败，请检查以上Git错误信息" -ForegroundColor Red
            exit 2
        }
        Write-Host "🔄 更新工作树到当前HEAD ($($previousHead.Substring(0,7)) -> $($currentHead.Substring(0,7)))"
    }
}

# 检查每日任务是否存在
$taskName = "每日运行自定义脚本_015aa3e1"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $existingTask) {
    $targetScript = Join-Path $targetDir "Invoke-DailyTask.ps1"
    # 创建新任务
    $action = New-ScheduledTaskAction -Execute "C:\Program Files\PowerShell\7\pwsh.exe" `
        -Argument "-File `"$targetScript`""
    
    $trigger = New-ScheduledTaskTrigger -Daily -At 00:00
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
    
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "每日执行维护脚本"
    
    Write-Host "✅ 计划任务已创建: $taskName"
}
else {
    Write-Host "⏩ 计划任务 $taskName 已存在，未做修改"
}
