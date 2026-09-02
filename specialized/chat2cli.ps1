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

    [System.Windows.Clipboard]::SetDataObject($data)
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




function Show-Chat2CLIToast {
    param(
        [string]$Message = "Chat2CLI 执行完成"
    )

    Add-Type -AssemblyName PresentationFramework
    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName WindowsBase

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

    # 居中偏下：水平居中，垂直位于工作区底部上方约 180px
    $workArea = [System.Windows.SystemParameters]::WorkArea
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
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
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

            $current = Get-Clipboard -Raw
            if ($null -eq $current) {
                $current = ""
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


