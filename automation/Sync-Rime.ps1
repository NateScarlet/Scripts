# 使用脚本块局部作用域避免污染调用环境
& {
    # 使用严格的错误处理
    $ErrorActionPreference = "Stop"
    function Invoke-NativeCommand {
        $command = $args[0]
        $arguments = $args[1..($args.Length-1)]
        
        & $command @arguments
        if ($LASTEXITCODE -ne 0) {
            Throw "命令 '$args' 失败 (退出码 $LASTEXITCODE)"
        }
    }
    
    # 查找 Weasel 安装路径
    $regPath = "HKLM:\SOFTWARE\WOW6432Node\Rime\Weasel"
    $root = (Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue).WeaselRoot

    if (!$root) {
        throw "Weasel not installed or registry key not found"
    }

    # 临时修改 PATH 环境变量（仅在当前作用域有效）
    $env:Path = "$root;$env:Path"

    # 定义同步目录
    $syncDir = Join-Path $env:APPDATA "Rime/sync"

    if (-not (Test-Path $syncDir)) {
        throw "Sync directory not found: $syncDir"
    }

    try {
        # 获取当前时间用于提交信息
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        
        # 切换到同步目录
        Push-Location $syncDir
        
        $env:GIT_AUTHOR_NAME = "Rime Sync Bot"
        $env:GIT_AUTHOR_EMAIL = "rime-sync-bot@invalid"
        $env:GIT_COMMITTER_NAME = "Rime Sync Bot"
        $env:GIT_COMMITTER_EMAIL = "rime-sync-bot@invalid"
        $env:GIT_CONFIG_COUNT = 1
        $env:GIT_CONFIG_KEY_0 = "commit.gpgSign"
        $env:GIT_CONFIG_VALUE_0 = "false"

        $statusOutput = Invoke-NativeCommand git status --porcelain
        if ([string]::IsNullOrWhiteSpace($statusOutput)) {
            Write-Host "无变更需要提交" -ForegroundColor Yellow
        }
        else {        
            Write-Host "Committing changes..."
            Invoke-NativeCommand git commit -a -m "Automatic sync at $timestamp"            
        }

        Write-Host "Pulling latest changes from remote..."
        Invoke-NativeCommand git pull --rebase
                
        Write-Host "Running WeaselDeployer..."
        WeaselDeployer.exe /sync

        Write-Host "Pushing changes..."
        Invoke-NativeCommand git push   

        Write-Host "Rime sync completed successfully." -ForegroundColor Green
    }
    finally {
        # 确保切换回原目录
        if (Get-Command Pop-Location -ErrorAction SilentlyContinue) {
            Pop-Location
        }
    }
}
