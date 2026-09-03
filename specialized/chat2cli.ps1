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

    # 居中偏下：水平居中，垂直位于用户当前鼠标所在屏幕的工作区底部上方约 180px。
    # 关键：Cursor.Position 和 Screen.WorkingArea 都基于物理像素，
    # 而 WPF 的 Left/Top 基于 DIP（逻辑像素）。在高 DPI 缩放下两者不一致，
    # 必须用 TransformFromDevice 把物理像素换算成 DIP，否则窗口会定位到屏幕外。
    $mousePosition = [System.Windows.Forms.Cursor]::Position
    $currentScreen = [System.Windows.Forms.Screen]::FromPoint($mousePosition)
    $workArea = $currentScreen.WorkingArea

    # 窗口显示后才存在 PresentationSource，用它做物理像素 -> DIP 的换算。
    # 用左上角和右下角两个点分别转换，得到正确的 DIP 矩形（宽高随缩放自动调整）。
    $source = [System.Windows.PresentationSource]::FromVisual($script:Chat2CLIToastWindow)
    if ($null -ne $source) {
        $transform = $source.CompositionTarget.TransformFromDevice
        $topLeftDip = $transform.Transform([System.Windows.Point]::new($workArea.Left, $workArea.Top))
        $bottomRightDip = $transform.Transform([System.Windows.Point]::new($workArea.Right, $workArea.Bottom))
        $workAreaDip = [System.Windows.Rect]::new(
            $topLeftDip.X,
            $topLeftDip.Y,
            $bottomRightDip.X - $topLeftDip.X,
            $bottomRightDip.Y - $topLeftDip.Y
        )
    }
    else {
        # 兜底：拿不到 source 时直接当 DIP 用（通常发生在窗口尚未真正显示时）
        $workAreaDip = [System.Windows.Rect]::new($workArea.X, $workArea.Y, $workArea.Width, $workArea.Height)
    }

    $script:Chat2CLIToastWindow.Left = $workAreaDip.Left + [Math]::Max(0, ($workAreaDip.Width - $script:Chat2CLIToastWindow.ActualWidth) / 2)
    $script:Chat2CLIToastWindow.Top = $workAreaDip.Bottom - 180 - $script:Chat2CLIToastWindow.ActualHeight
}

function Update-Chat2CLIToast {
    param([string]$Message)

    if ($null -ne $script:Chat2CLIToastWindow -and $null -ne $script:Chat2CLIToastText) {
        $script:Chat2CLIToastText.Text = $Message

        # 强制 WPF 同步完成布局与渲染，确保文字立即显示。
        # 否则紧随其后的 Start-Sleep 会阻塞 Dispatcher，
        # 更新永远来不及绘制就被 Hide 了。
        $script:Chat2CLIToastWindow.Dispatcher.Invoke([Action]{}, [System.Windows.Threading.DispatcherPriority]::Render)
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
        # 使用不带 BOM 的 UTF-8。Encoding.UTF8 自带 BOM，会往 stdin 写入
        # EF BB BF 前缀，导致子进程收到多余的 U+FEFF。
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $psi.StandardInputEncoding = $utf8NoBom
        $psi.StandardOutputEncoding = $utf8NoBom
        $psi.StandardErrorEncoding = $utf8NoBom
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

            # 注册异步任务到脚本作用域，供 finally 块在异常时清理。
            # Ctrl+C 中断时这些任务可能仍在管道上等待读取，
            # 必须在释放进程前等待它们结束，否则句柄残留。
            $script:Chat2CLIAsyncTasks = @($stdoutTask, $stderrLineTask)

            while (-not $process.HasExited) {
                # 持续读取直到当前没有可用的行，避免每次只读一行后固定睡眠，
                # 输出量大时被 20ms 睡眠严重拖慢吞吐。
                while ($stderrLineTask.IsCompleted) {
                    $stderrLine = $stderrLineTask.Result
                    if ($null -ne $stderrLine) {
                        Write-Host $stderrLine
                        $stderrLineTask = $process.StandardError.ReadLineAsync()
                    }
                    else {
                        # ReadLineAsync 返回 null 表示已到流末尾
                        break
                    }
                }
                if ($process.HasExited) {
                    break
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
            # Ctrl+C 可能中断在异步读取途中，必须显式取消并等待，
            # 否则底层管道句柄会残留，导致后续进程报"Read 被占用"。

            # 先等待异步读取任务结束。进程被 Kill 后，管道会收到 EOF，
            # 任务自然完成；此处设置超时避免极端情况下无限等待。
            if ($null -ne $script:Chat2CLIAsyncTasks) {
                foreach ($asyncTask in $script:Chat2CLIAsyncTasks) {
                    if ($null -ne $asyncTask -and -not $asyncTask.IsCompleted) {
                        try {
                            $asyncTask.Wait(2000) | Out-Null
                        }
                        catch {
                            # 任务可能因进程被杀而抛出异常，忽略即可
                        }
                    }
                }
                $script:Chat2CLIAsyncTasks = $null
            }

            if (-not $process.HasExited) {
                try {
                    $process.Kill()
                }
                catch {
                    # 进程可能已自然退出，Kill 抛出的异常可以忽略
                }
            }
            # 等待进程完全退出，确保所有句柄释放
            if (-not $process.WaitForExit(5000)) {
                Write-Warning "[Watch-Chat2CLI] 子进程未在 5 秒内退出，强制终止可能不完整"
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
            # 使用 UnicodeText 而不是 Text：Text 是 ANSI 格式（CF_TEXT），
            # 中文会乱码；UnicodeText（CF_UNICODETEXT）与 Get-Clipboard 一致。
            if ($null -ne $data -and $data.GetDataPresent([System.Windows.DataFormats]::UnicodeText)) {
                $current = [string]$data.GetData([System.Windows.DataFormats]::UnicodeText)
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


