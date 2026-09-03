function Invoke-Chat2CLI {
    $output = Get-Clipboard | uv run $PSScriptRoot/chat2cli.py @args
    if ($LASTEXITCODE -ne 0) {
        throw "chat2cli process failed with exit code $LASTEXITCODE"
    }
    if ($output -is [array]) {
        $output = $output -join "`n"
    }
    Set-Chat2CLIClipboard $output
}

Set-Alias "chat2cli" Invoke-Chat2CLI


# 剪贴板被其他进程占用时，Win32 剪贴板 API 会返回 CLIPBRD_E_CANT_OPEN。
# 通过带退避的重试循环获取剪贴板访问权，而不是直接失败。
function Invoke-Chat2CLIClipboardWithRetry {
    param(
        [scriptblock]$Action,
        [int]$MaxAttempts = 10,
        [int]$RetryDelayMilliseconds = 100
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return & $Action
        }
        catch [System.Runtime.InteropServices.COMException] {
            if ($attempt -eq $MaxAttempts) {
                throw
            }
            Start-Sleep -Milliseconds $RetryDelayMilliseconds
        }
    }
}

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

    Invoke-Chat2CLIClipboardWithRetry { [System.Windows.Clipboard]::SetDataObject($data) }
}

function Test-Chat2CLIClipboardGenerated {
    Add-Type -AssemblyName PresentationCore

    $data = Invoke-Chat2CLIClipboardWithRetry { [System.Windows.Clipboard]::GetDataObject() }
    if ($null -eq $data) {
        return $false
    }

    if ($data.GetDataPresent('HTML Format')) {
        return ([string]$data.GetData('HTML Format')) -match 'chat2cli-generated'
    }

    return $false
}




function Show-Chat2CLIToast {
    param(
        [string]$Message = "Chat2CLI 执行完成"
    )

    Add-Type -AssemblyName PresentationFramework
    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName WindowsBase
    Add-Type -AssemblyName System.Windows.Forms

    if ($null -eq $script:Chat2CLIToastWindow) {
        $script:Chat2CLIToastWindow = New-Object System.Windows.Window
        $script:Chat2CLIToastWindow.WindowStyle = 'None'
        $script:Chat2CLIToastWindow.AllowsTransparency = $true
        $script:Chat2CLIToastWindow.Background = [System.Windows.Media.Brushes]::Transparent
        $script:Chat2CLIToastWindow.ShowInTaskbar = $false
        $script:Chat2CLIToastWindow.Topmost = $true
        $script:Chat2CLIToastWindow.SizeToContent = 'WidthAndHeight'

        $script:Chat2CLIToastBorder = New-Object System.Windows.Controls.Border
        $script:Chat2CLIToastBorder.Background = New-Object System.Windows.Media.SolidColorBrush([System.Windows.Media.Color]::FromArgb(220, 30, 30, 30))
        $script:Chat2CLIToastBorder.CornerRadius = New-Object System.Windows.CornerRadius(10)
        $script:Chat2CLIToastBorder.Padding = New-Object System.Windows.Thickness(24, 12, 24, 12)

        $script:Chat2CLIToastText = New-Object System.Windows.Controls.TextBlock
        $script:Chat2CLIToastText.Foreground = [System.Windows.Media.Brushes]::White
        $script:Chat2CLIToastText.FontSize = 16
        $script:Chat2CLIToastText.FontFamily = 'Microsoft YaHei'

        $script:Chat2CLIToastBorder.Child = $script:Chat2CLIToastText
        $script:Chat2CLIToastWindow.Content = $script:Chat2CLIToastBorder
        $script:Chat2CLIToastWindow.WindowStartupLocation = 'Manual'
    }

    $script:Chat2CLIToastText.Text = $Message

    if (-not $script:Chat2CLIToastWindow.IsVisible) {
        $script:Chat2CLIToastWindow.Show()
    }

    # 居中偏下：水平居中，垂直位于用户当前鼠标所在屏幕的工作区底部上方约 180px
    $mousePosition = [System.Windows.Forms.Cursor]::Position
    $currentScreen = [System.Windows.Forms.Screen]::FromPoint($mousePosition)
    $workArea = $currentScreen.WorkingArea
    $script:Chat2CLIToastWindow.Left = $workArea.Left + [Math]::Max(0, ($workArea.Width - $script:Chat2CLIToastWindow.ActualWidth) / 2)
    $script:Chat2CLIToastWindow.Top = $workArea.Bottom - 180 - $script:Chat2CLIToastWindow.ActualHeight
}

function Update-Chat2CLIToast {
    param([string]$Message)

    if ($null -ne $script:Chat2CLIToastWindow -and $null -ne $script:Chat2CLIToastText) {
        $script:Chat2CLIToastText.Text = $Message
    }
}

function Hide-Chat2CLIToast {
    if ($null -ne $script:Chat2CLIToastWindow -and $script:Chat2CLIToastWindow.IsVisible) {
        $script:Chat2CLIToastWindow.Hide()
    }
}

function Watch-Chat2CLI {
    param(
        [int]$IntervalMilliseconds = 500
    )

    $scriptPath = "$PSScriptRoot/chat2cli.py"
    $currentPid = $PID

    function Invoke-Chat2CLIProcess {
        param(
            [string]$InputText,
            [switch]$SuppressToast
        )

        if (-not $SuppressToast) {
            Show-Chat2CLIToast -Message "正在处理..."
        }

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "uv"
        $psi.Arguments = "run `"$scriptPath`""
        $psi.WorkingDirectory = (Get-Location).Path
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        # 重定向 stderr，由主线程轮询逐行读取并原样输出。
        # 不重定向时 .NET 在交互式 PowerShell 中不会把子进程 stderr
        # 可靠流回当前终端，导致实时日志丢失。
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.StandardInputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $psi.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi
        $process.Start() | Out-Null

        try {
            $process.StandardInput.Write($InputText)
            $process.StandardInput.Close()

            $stdoutTask = $process.StandardOutput.ReadToEndAsync()

            # stderr 在主线程轮询逐行读取，原样输出，保留 ANSI 颜色。
            # 顺序由读取时机保证，不会像事件队列那样乱序。
            $stderrLineTask = $process.StandardError.ReadLineAsync()

            while (-not $process.HasExited) {
                if ($stderrLineTask.IsCompleted) {
                    $stderrLine = $stderrLineTask.Result
                    if ($null -ne $stderrLine) {
                        Write-Host $stderrLine
                        $stderrLineTask = $process.StandardError.ReadLineAsync()
                    }
                }
                Start-Sleep -Milliseconds 20
            }

            # 进程退出后，把 stderr 剩余的行全部读出。
            # 最后一个异步读可能仍占用流，先等它完成，避免同步 ReadLine 抛异常。
            if (-not $stderrLineTask.IsCompleted) {
                $stderrLineTask.Wait()
            }
            if ($null -ne $stderrLineTask.Result) {
                Write-Host $stderrLineTask.Result
            }
            while (-not $process.StandardError.EndOfStream) {
                $remainingLine = $process.StandardError.ReadLine()
                if ($null -ne $remainingLine) {
                    Write-Host $remainingLine
                }
            }

            # 确保子进程完全退出后再读取 stdout 结果
            $process.WaitForExit()

            $output = $stdoutTask.Result

            if ($output) {
                Set-Chat2CLIClipboard $output
            }

            if ($process.ExitCode -ne 0) {
                throw "chat2cli process failed with exit code $($process.ExitCode)"
            }

            if (-not $SuppressToast) {
                Update-Chat2CLIToast -Message "Chat2CLI 执行完成"
                Start-Sleep -Milliseconds 1800
                Hide-Chat2CLIToast
            }

            return $output
        }
        finally {
            if (-not $process.HasExited) {
                $process.Kill()
            }
            $process.Dispose()
            Hide-Chat2CLIToast
        }
    }

    # 检查剪贴板是否被其他进程占用
    function Test-Chat2CLIConflict {
        param([string]$ClipboardText)

        if ([string]::IsNullOrEmpty($ClipboardText)) {
            return $false
        }

        # 匹配格式: [<进程ID>] chat2cli: ...
        if ($ClipboardText -match '^\[(\d+)\] chat2cli:') {
            $otherPid = [int]$Matches[1]
            # 如果是其他进程（不是当前进程），则存在冲突
            return $otherPid -ne $currentPid
        }

        return $false
    }

    # 设置占位文本
    function Set-Chat2CLIPlaceholder {
        $placeholder = "[$currentPid] chat2cli: 正在处理中..."
        Set-Chat2CLIClipboard $placeholder
    }

    # 使用命名互斥体与停止事件，确保同一时间只有一个监听实例
    $mutexName = "Global\Chat2CLI.Watch.Mutex"
    $stopEventName = "Global\Chat2CLI.Watch.Stop"

    $watchMutex = New-Object System.Threading.Mutex($false, $mutexName)
    $stopEvent = New-Object System.Threading.EventWaitHandle($false, [System.Threading.EventResetMode]::ManualReset, $stopEventName)
    $ownsMutex = $false

    try {
        if (-not $watchMutex.WaitOne(0)) {
            Write-Host "[Watch-Chat2CLI] 检测到已有监听实例，正在停止前一个实例..."
            $stopEvent.Set() | Out-Null
            $watchMutex.WaitOne() | Out-Null
            Write-Host "[Watch-Chat2CLI] 前一个实例已停止"
        }
        $ownsMutex = $true
        $stopEvent.Reset() | Out-Null

        Write-Host '[Watch-Chat2CLI] 已启动，监听剪贴板等待新的 chat2cli 调用...'

        # 忽略开始前剪贴板的内容：用空字符串生成初始指令
        Invoke-Chat2CLIProcess -InputText "" -SuppressToast | Out-Null

        while ($true) {
            if ($stopEvent.WaitOne(0)) {
                Write-Host "[Watch-Chat2CLI] 收到停止信号，正在退出..."
                break
            }

            # 使用带重试的原生方法避免其他进程占用剪贴板导致的瞬时失败
            $data = Invoke-Chat2CLIClipboardWithRetry { [System.Windows.Clipboard]::GetDataObject() }
            $current = ""
            if ($null -ne $data -and $data.GetDataPresent([System.Windows.DataFormats]::Text)) {
                $current = [string]$data.GetData([System.Windows.DataFormats]::Text)
            }

            # 检查是否有其他 chat2cli 监控进程的占位文本
            if (Test-Chat2CLIConflict -ClipboardText $current) {
                Write-Host "[Watch-Chat2CLI] 检测到其他监控进程正在处理，为避免冲突自动退出"
                break
            }

            if (-not (Test-Chat2CLIClipboardGenerated)) {
                # 忽略包含指令提示的输入（初始指令和错误指令都包裹在
                # <chat2cli_instruction> 标签内，其中的示例不应触发执行）
                $isInstruction = $current.Contains('<chat2cli_instruction>')

                if (-not $isInstruction) {
                    # 必须匹配完整的 chat2cli fenced block（三个或更多反引号）。
                    # 这里只做粗筛触发，围栏长度一致性由 chat2cli.py 精确解析。
                    $hasToolBlock = $current -match '(?ms)^`{3,}chat2cli\s*$.*?^`{3,}\s*$'

                    if ($hasToolBlock) {
                        # 发现新的 chat2cli 内容，先设置占位文本
                        Set-Chat2CLIPlaceholder
                        # 然后执行处理
                        Invoke-Chat2CLIProcess -InputText $current | Out-Null
                    }
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
    finally {
        if ($ownsMutex) {
            $watchMutex.ReleaseMutex()
        }
        $watchMutex.Dispose()
        $stopEvent.Dispose()
        Hide-Chat2CLIToast
    }
}


