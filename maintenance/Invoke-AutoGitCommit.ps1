# Invoke-AutoGitCommit.ps1 - 自动提交多个 Git 仓库的脚本
# 版本：pwsh 7

# 使用脚本块局部作用域避免污染调用环境
& {
    # 设置严格的错误处理
    $ErrorActionPreference = "Stop"

    # 获取脚本所在目录
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) { $scriptDir = Get-Location }
    
    # 配置文件名 (PSD1格式)
    $configFile = "~/auto-git-commit.config.8b4e8ac19dc5.psd1"
    
    # 如果配置文件不存在，则创建默认配置
    if (-not (Test-Path $configFile)) {
        Write-Host "未找到配置文件，正在创建默认配置..." -ForegroundColor Yellow
        
        # 创建带有详细注释的默认配置文件
        $defaultConfigContent = @'
# 自动提交脚本配置文件

@{
    # 需要自动提交的Git仓库路径列表
    repositories = @(
    )

    # Git提交时使用的用户名
    gitName = 'Auto Commit Bot'
    
    # Git提交时使用的邮箱
    gitEmail = 'auto-commit-bot@invalid'  
    
    # 提交信息模板，{timestamp}会被替换为实际时间
    commitMessage = 'Automatic commit at {timestamp}' 
    
    # 是否在提交前尝试拉取变更（推荐启用以避免冲突）
    attemptPullFirst = $true
}
'@
        
        $defaultConfigContent | Out-File $configFile -Encoding UTF8
        Write-Host "已创建默认配置文件: $configFile" -ForegroundColor Green
        Write-Host "请编辑此文件并配置您的仓库路径后再运行脚本" -ForegroundColor Cyan
        exit 0
    }

    # 加载配置文件 (使用安全的数据文件加载方式)
    try {
        $config = Import-PowerShellDataFile -Path $configFile
    }
    catch {
        throw "配置文件格式错误: $_"
    }

    # 验证配置
    if (-not $config.repositories -or $config.repositories.Count -eq 0) {
        # 可能就是不需要同步仓库 
        Write-Host "配置文件 $configFile 中未定义任何仓库路径"
        exit 0
    }

    # 设置默认值
    if (-not $config.gitName) { $config.gitName = "Auto Commit Bot" }
    if (-not $config.gitEmail) { $config.gitEmail = "auto-commit-bot@invalid" }
    if (-not $config.commitMessage) { $config.commitMessage = "Automatic commit at {timestamp}" }

    # 处理每个仓库
    $results = [System.Collections.Generic.List[object]]::new()
    
    foreach ($repoPath in $config.repositories) {
        $result = [PSCustomObject]@{
            Repository = $repoPath
            Success    = $false
            Message    = "尚未处理"
            StartTime  = (Get-Date)
        }
        
        $resultDetails = $null
        try {
            Write-Host "`n正在处理仓库: $repoPath" -ForegroundColor Cyan
            
            # 验证仓库路径是否存在
            if (-not (Test-Path $repoPath)) {
                throw "目录不存在"
            }
            
            # 检查是否为 Git 仓库
            $gitDir = Join-Path $repoPath ".git"
            if (-not (Test-Path $gitDir)) {
                throw "不是有效的 Git 仓库"
            }
            
            # 设置当前工作目录
            Push-Location $repoPath
            
            # 配置 Git 用户信息
            $env:GIT_AUTHOR_NAME = $config.gitName
            $env:GIT_AUTHOR_EMAIL = $config.gitEmail
            $env:GIT_COMMITTER_NAME = $config.gitName
            $env:GIT_COMMITTER_EMAIL = $config.gitEmail

            # 执行拉取操作（如果需要）
            if ($config.attemptPullFirst) {
                Write-Host "正在拉取最新变更..."
                git pull --rebase --quiet 2>$null
            }
            
            # 检查是否有变更
            $statusOutput = git status --porcelain 2>$null
            if ([string]::IsNullOrWhiteSpace($statusOutput)) {
                Write-Host "无变更需要提交" -ForegroundColor Yellow
                $result.Success = $true
                $result.Message = "无变更"
                $resultDetails = $null
            }
            else {
                # 替换提交消息中的时间戳
                $commitMsg = $config.commitMessage.Replace("{timestamp}", $(Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
                
                # 执行 Git 操作
                Write-Host "添加所有变更..."
                git add -A --quiet 2>$null
                
                Write-Host "创建提交: $commitMsg"
                git commit -m $commitMsg --quiet 2>$null
                
                Write-Host "推送变更..."
                git push --quiet 2>$null
                
                $result.Success = $true
                $result.Message = "提交成功"
            }
            
            Write-Host "仓库 $repoPath 处理成功" -ForegroundColor Green
        }
        catch {
            $result.Message = "处理失败"
            $resultDetails = $_.Exception
            Write-Host "处理失败: $repoPath" -ForegroundColor Red
            Write-Host "错误详情: $($_.Exception.Message)" -ForegroundColor Red
        }
        finally {
            # 确保切换回原目录
            try { Pop-Location -ErrorAction SilentlyContinue } catch {}
            
            # 添加处理时间
            $result | Add-Member -NotePropertyName "Duration" -NotePropertyValue (New-TimeSpan -Start $result.StartTime)
            
            # 添加原始错误信息（如有）
            if ($resultDetails) {
                $result | Add-Member -NotePropertyName "Error" -NotePropertyValue $resultDetails
            }
            
            $results.Add($result)
        }
    }
    
    # 输出摘要报告
    Write-Host "`n`n任务摘要:" -ForegroundColor Cyan
    Write-Host ("=" * 100)
    
    foreach ($r in $results) {
        $durationFmt = "{0:hh\:mm\:ss\.fff}" -f $r.Duration
        $status = if ($r.Success) { "✔" } else { "✗" }
        $color = if ($r.Success) { "Green" } else { "Red" }
        
        $output = "[$status] $($r.Repository) - $($r.Message) (用时: $durationFmt)"
        if ($r.Error) {
            $output += "`n  错误详情: $($r.Error.Message)"
        }
        
        Write-Host $output -ForegroundColor $color
    }
    
    Write-Host ("=" * 100)
    
    # 统计结果
    $successCount = ($results | Where-Object { $_.Success }).Count
    $failureCount = $results.Count - $successCount
    $totalDuration = (New-TimeSpan -Start ($results[0].StartTime) -End (Get-Date)).ToString("hh\:mm\:ss")
    
    Write-Host ("处理完成. 总计: {0} 成功: {1} 失败: {2} 总耗时: {3}" -f 
        $results.Count, 
        $successCount, 
        $failureCount,
        $totalDuration) -ForegroundColor Cyan
    
    # 如果有失败项目则返回非零退出码
    if ($failureCount -gt 0) {
        exit $failureCount
    }
}
