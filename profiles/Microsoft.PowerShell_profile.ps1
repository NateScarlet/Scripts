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
    $output = Get-Clipboard | py $ScriptsRoot/specialized/chat2cli.py
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
    Set-Chat2CLIClipboard $output
}

Set-Alias "chat2cli" Invoke-Chat2CLI


function Set-Chat2CLIClipboard {
    param([string]$Text)

    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName System.Web

    $encoded = [System.Web.HttpUtility]::HtmlEncode($Text)
    $htmlBody = "<html><body><!-- chat2cli-generated --><!--StartFragment--><pre>$encoded</pre><!--EndFragment--></body></html>"

    $prefix = "Version:0.9`r`n"
    $headerLength = $prefix.Length + "StartHTML:00000000`r`nEndHTML:00000000`r`nStartFragment:00000000`r`nEndFragment:00000000`r`n".Length

    $startHtml = $headerLength
    $htmlBytes = [System.Text.Encoding]::UTF8.GetBytes($htmlBody)
    $endHtml = $startHtml + $htmlBytes.Length

    $fragmentStartMarker = '<!--StartFragment-->'
    $fragmentEndMarker = '<!--EndFragment-->'
    $fragmentStart = $startHtml + [System.Text.Encoding]::UTF8.GetByteCount($htmlBody.Substring(0, $htmlBody.IndexOf($fragmentStartMarker) + $fragmentStartMarker.Length))
    $fragmentEnd = $startHtml + [System.Text.Encoding]::UTF8.GetByteCount($htmlBody.Substring(0, $htmlBody.IndexOf($fragmentEndMarker)))

    $html = "Version:0.9`r`n" +
        "StartHTML:$('{0:D8}' -f $startHtml)`r`n" +
        "EndHTML:$('{0:D8}' -f $endHtml)`r`n" +
        "StartFragment:$('{0:D8}' -f $fragmentStart)`r`n" +
        "EndFragment:$('{0:D8}' -f $fragmentEnd)`r`n" +
        $htmlBody

    $data = New-Object System.Windows.DataObject
    $data.SetText($Text)
    $data.SetData('HTML Format', $html)

    [System.Windows.Clipboard]::SetDataObject($data, $true)
}

function Test-Chat2CLIClipboardGenerated {
    Add-Type -AssemblyName PresentationCore

    $data = [System.Windows.Clipboard]::GetDataObject()
    if ($null -eq $data) {
        return $false
    }

    if ($data.GetDataPresent('HTML Format')) {
        return ([string]$data.GetData('HTML Format')) -match 'chat2cli-generated'
    }

    return $false
}



function Watch-Chat2CLI {
    param(
        [int]$IntervalMilliseconds = 500
    )

    $scriptPath = "$ScriptsRoot/specialized/chat2cli.py"

    function Invoke-Chat2CLIProcess {
        $clipboard = Get-Clipboard -Raw
        if ($null -eq $clipboard) {
            $clipboard = ""
        }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "py"
        $psi.Arguments = "`"$scriptPath`""
        $psi.WorkingDirectory = (Get-Location).Path
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $psi.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi
        $process.Start() | Out-Null

        try {
            $process.StandardInput.Write($clipboard)
            $process.StandardInput.Close()

            $stdoutTask = $process.StandardOutput.ReadToEndAsync()
            $stderrTask = $process.StandardError.ReadToEndAsync()

            while (-not $process.HasExited) {
                Start-Sleep -Milliseconds 100
            }

            $output = $stdoutTask.Result
            $errorOutput = $stderrTask.Result

            if ($output) {
                Set-Chat2CLIClipboard $output
            }

            if ($errorOutput) {
                Write-Host $errorOutput -ForegroundColor Red
            }

            if ($process.ExitCode -ne 0) {
                throw "Command failed with exit code $($process.ExitCode)"
            }
        }
        finally {
            if (-not $process.HasExited) {
                $process.Kill()
            }
            $process.Dispose()
        }
    }

    Write-Host '[Watch-Chat2CLI] 已启动，监听剪贴板等待新的 tool 调用...'

    try {
        # 启动时处理当前剪贴板：无 tool 请求时由 chat2cli.py 生成初始指令
        Invoke-Chat2CLIProcess

        while ($true) {
            $current = Get-Clipboard -Raw

            if (-not (Test-Chat2CLIClipboardGenerated)) {
                # 必须匹配完整的 ```tool fenced block，避免误触发 ```tool-result
                $hasToolBlock = $current -match '(?ms)^```tool\s*$.*?^```\s*$'

                if ($hasToolBlock) {
                    Invoke-Chat2CLIProcess
                }
            }

            Start-Sleep -Milliseconds $IntervalMilliseconds
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host "[Watch-Chat2CLI] 已停止"
    }
    catch [System.OperationCanceledException] {
        Write-Host "[Watch-Chat2CLI] 已停止"
    }
}




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
