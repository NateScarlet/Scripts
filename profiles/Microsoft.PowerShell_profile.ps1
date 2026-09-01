# https://github.com/PowerShell/PSReadLine/issues/779
$OutputEncoding = [System.Text.Encoding]::UTF8
[System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[System.Console]::InputEncoding = [System.Text.Encoding]::UTF8

# Refresh env
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# https://bugs.python.org/issue42627
# 获取 Internet 设置的注册表项
$proxySettings = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
# 检查是否启用了代理
if ($proxySettings.ProxyEnable -eq 1) {
    $env:HTTP_PROXY = $proxySettings.ProxyServer
    $env:HTTPS_PROXY = $proxySettings.ProxyServer
    $env:NO_PROXY = "localhost,127.0.0.1,::1,0.0.0.0,$(
        ($proxySettings.ProxyOverride -split ';' | ForEach-Object { $_ `
            -replace '^(\*\.)+','.' `
            -replace '^(\d+)(?:\.\*){1,3}$','$1.0.0.0/8' `
            -replace '^(\d+)\.(\d+)(?:\.\*){1,2}$','$1.$2.0.0/16' `
            -replace '^(\d+)\.(\d+)\.(\d+)\.\*$','$1.$2.$3.0/8' `
        }) -join ',' 
        )"
} 

if (-not $env:ANTIGRAVITY_AGENT) {
    try {
        Import-Module PSReadLine -ErrorAction Stop
    }
    catch {
        Write-Host "[提示] 命令行增强功能未启用: $_" -ForegroundColor DarkGray
        Write-Host "      运行: Install-Module PSReadLine -Scope CurrentUser" -ForegroundColor Cyan
    }


    $poshGitAvailable = $false
    try {
        Import-Module posh-git -ErrorAction Stop
        $poshGitAvailable = $true
    }
    catch {
        Write-Host "[提示] Git 状态支持未启用: $_" -ForegroundColor DarkGray
        Write-Host "      运行: Install-Module posh-git -Scope CurrentUser" -ForegroundColor Cyan
    }

    $ScriptsRoot = Resolve-Path "$PSScriptRoot/.."
    $ScriptLib = Resolve-Path "$PSScriptRoot/../lib"

    function global:prompt {
        # 获取当前路径并简化显示 
        # 每个盘符可能都建了个人文件夹　所以要保留盘符显示
        $currentPath = (Get-Location).Path -replace [regex]::Escape(($env:USERPROFILE -replace '^.+:', ':')), ":\~" 
        
        # 添加 Git 状态信息（如果 posh-git 已加载）
        $gitStatus = if ($poshGitAvailable) {
            try {
                # 直接调用 Write-VcsStatus，不依赖 $global:GitStatus
                Write-VcsStatus
            }
            catch {
                "" # 调用失败时返回空字符串
            }
        }
        
        # 组合最终提示
        "PS ${currentPath}${gitStatus}> "
    }
} else {
    $ScriptsRoot = Resolve-Path "$PSScriptRoot/.."
    $ScriptLib = Resolve-Path "$PSScriptRoot/../lib"
}

function New-FileByReplace {
    py $ScriptLib/generate-by-replace.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Set-Alias "generate:replace" New-FileByReplace

function Start-WaitIdle {
    py $ScriptLib/wait-idle.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Set-Alias "wait-idle" Start-WaitIdle



function Start-ComfyRename {
    py $ScriptsRoot/specialized/comfy_ui/rename.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Set-Alias "comfy-rename" Start-ComfyRename


function Start-ComfySearch {
    py $ScriptsRoot/specialized/comfy_ui/search.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Set-Alias "comfy-search" Start-ComfySearch


function Remove-Duplicated-File {
    py $ScriptLib/remove-duplicated-file.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Update-File-Number {
    py $ScriptLib/renumber-files.py $args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Remove-Empty-Dir {
    Get-ChildItem -Directory $args | Where-Object { $_.GetFiles().Count -eq 0 -and $_.GetDirectories().Count -eq 0 } | ForEach-Object { $_; Remove-Item $_ }
}

function Invoke-Chat2CLI {
    Get-Clipboard | py $ScriptsRoot/specialized/chat2cli.py | Set-Clipboard
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Set-Alias "chat2cli" Invoke-Chat2CLI

. "$ScriptLib/New-GitWorkspace.ps1"

#region 远程 VSCode 会话防休眠
# 仅在“正通过浏览器版 VSCode (code serve-web) 操作本机”时自动阻止空闲休眠。
# 判定逻辑自包含在 Test-IsServeWebSession：先用 TERM_PROGRAM 快速排除非 VSCode 终端，
# 再沿父进程链区分 serve-web 服务端与桌面版 Code。
# 请求随本 pwsh 进程结束自动释放，手动开关见 lib/NoSleep.ps1（Enable/Disable-NoSleep）。
. "$ScriptLib/NoSleep.ps1"
if (Test-IsServeWebSession) {
    # 原因会附带时间与 pid 显示在 powercfg /requests 中
    Enable-NoSleep -Reason 'code serve-web 会话'
    # 遗弃终端自杀看门狗：会话被取代且闲置超时后自动退出（NO_SLEEP_WATCHDOG_OFF=1 禁用）
    Enable-NoSleepWatchdog
}
#endregion
