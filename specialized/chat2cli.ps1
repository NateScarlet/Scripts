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

function Get-Chat2CLIClipboardText {
    Add-Type -AssemblyName PresentationCore

    $data = Invoke-Chat2CLIClipboardWithRetry { [System.Windows.Clipboard]::GetDataObject() }
    if ($null -eq $data) {
        return ""
    }

    if ($data.GetDataPresent([System.Windows.DataFormats]::UnicodeText)) {
        return [string]$data.GetData([System.Windows.DataFormats]::UnicodeText)
    }

    return ""
}

function Get-Chat2CLIPlaceholderPid {
    param([string]$ClipboardText)

    if ([string]::IsNullOrEmpty($ClipboardText)) {
        return $null
    }

    # 匹配格式: [<进程ID>] chat2cli: ...
    if ($ClipboardText -match '^\[(\d+)\] chat2cli:') {
        return [int]$Matches[1]
    }

    return $null
}




# 跨线程共享状态：toast 在独立 STA Runspace 中运行 WPF 消息循环，
# 主线程只写入命令和消息，由 Runspace 内的 DispatcherTimer 轮询消费。
# 使用 ConcurrentDictionary 保证线程安全。
$script:Chat2CLIToastState = $null

function Start-Chat2CLIToastThread {
    # Runspace 已存在且仍打开时直接返回
    if ($null -ne $script:Chat2CLIToastState) {
        $existingRs = $null
        if ($script:Chat2CLIToastState.TryGetValue('Runspace', [ref]$existingRs)) {
            if ($null -ne $existingRs -and $existingRs.RunspaceStateInfo.State -eq 'Opened') {
                return
            }
        }
    }

    $state = [System.Collections.Concurrent.ConcurrentDictionary[string, object]]::new()
    $script:Chat2CLIToastState = $state

    # 主线程写入的命令和消息，Runspace 内轮询消费
    $state['Command'] = 'none'
    $state['Message'] = ''

    # 创建独立 STA Runspace，避免与 PowerShell 主线程竞争 WPF Dispatcher，
    # 从而消除 Ctrl+C 无响应和日志不刷新的问题。
    $runspace = [runspacefactory]::CreateRunspace()
    $runspace.ApartmentState = [System.Threading.ApartmentState]::STA
    $runspace.ThreadOptions = 'ReuseThread'
    $runspace.Open()

    $ps = [powershell]::Create()
    $ps.Runspace = $runspace

    $state['PowerShell'] = $ps
    $state['Runspace'] = $runspace

    # 在 STA Runspace 中执行 WPF 设置并启动 DispatcherTimer 轮询命令。
    # 脚本阻塞在 Dispatcher.Run()，直到收到 stop 命令后 BeginInvokeShutdown。
    $null = $ps.AddScript({
        param($st)

        Add-Type -AssemblyName PresentationFramework
        Add-Type -AssemblyName PresentationCore
        Add-Type -AssemblyName WindowsBase
        Add-Type -AssemblyName System.Windows.Forms

        $window = [System.Windows.Window]::new()
        $window.WindowStyle = 'None'
        $window.AllowsTransparency = $true
        $window.Background = [System.Windows.Media.Brushes]::Transparent
        $window.ShowInTaskbar = $false
        $window.Topmost = $true
        $window.SizeToContent = 'WidthAndHeight'

        $border = [System.Windows.Controls.Border]::new()
        $border.Background = [System.Windows.Media.SolidColorBrush]::new(
            [System.Windows.Media.Color]::FromArgb(220, 30, 30, 30)
        )
        $border.CornerRadius = [System.Windows.CornerRadius]::new(10)
        $border.Padding = [System.Windows.Thickness]::new(24, 12, 24, 12)

        $textBlock = [System.Windows.Controls.TextBlock]::new()
        $textBlock.Foreground = [System.Windows.Media.Brushes]::White
        $textBlock.FontSize = 16
        $textBlock.FontFamily = 'Microsoft YaHei'

        $border.Child = $textBlock
        $window.Content = $border
        $window.WindowStartupLocation = 'Manual'

        $st['Window'] = $window
        $st['Text'] = $textBlock
        $st['Ready'] = $true

        # 轮询主线程写入的命令。全部操作在 Runspace 的 STA 线程内执行，
        # 不涉及跨线程 scriptblock 委托。
        $timer = [System.Windows.Threading.DispatcherTimer]::new()
        $timer.Interval = [TimeSpan]::FromMilliseconds(50)

        $timer.Add_Tick({
            $cmd = $null
            if (-not $st.TryGetValue('Command', [ref]$cmd)) { return }
            if ($null -eq $cmd -or $cmd -eq 'none') { return }

            # 读取命令后立即复位，避免重复执行
            $cmdValue = $cmd
            $st['Command'] = 'none'

            $win = $null
            $txt = $null
            if (-not $st.TryGetValue('Window', [ref]$win) -or $null -eq $win) { return }
            if (-not $st.TryGetValue('Text', [ref]$txt) -or $null -eq $txt) { return }

            switch ($cmdValue) {
                'show' {
                    $msg = $st['Message']
                    $txt.Text = $msg

                    if (-not $win.IsVisible) {
                        $win.Show()
                    }

                    # 窗口定位必须在窗口所属线程内执行
                    $mousePosition = [System.Windows.Forms.Cursor]::Position
                    $currentScreen = [System.Windows.Forms.Screen]::FromPoint($mousePosition)
                    $workArea = $currentScreen.WorkingArea

                    $source = [System.Windows.PresentationSource]::FromVisual($win)
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
                        $workAreaDip = [System.Windows.Rect]::new($workArea.X, $workArea.Y, $workArea.Width, $workArea.Height)
                    }

                    $win.Left = $workAreaDip.Left + [Math]::Max(0, ($workAreaDip.Width - $win.ActualWidth) / 2)
                    $win.Top = $workAreaDip.Bottom - 180 - $win.ActualHeight
                }
                'update' {
                    $txt.Text = $st['Message']
                }
                'hide' {
                    if ($win.IsVisible) {
                        $win.Hide()
                    }
                }
                'stop' {
                    $timer.Stop()
                    if ($win.IsVisible) {
                        $win.Close()
                    }
                    # 关闭 Dispatcher 消息循环，使 Dispatcher.Run() 返回、
                    # 脚本结束、BeginInvoke 完成。
                    $currentDispatcher = [System.Windows.Threading.Dispatcher]::CurrentDispatcher
                    $currentDispatcher.BeginInvokeShutdown([System.Windows.Threading.DispatcherPriority]::Send)
                }
            }
        })

        $timer.Start()

        # 阻塞在消息循环，直到 stop 命令触发 BeginInvokeShutdown。
        [System.Windows.Threading.Dispatcher]::Run()
    })

    $null = $ps.AddArgument($state)
    $asyncResult = $ps.BeginInvoke()
    $state['AsyncResult'] = $asyncResult

    # 等待 Runspace 初始化 WPF 窗口（最多 5 秒）
    $ready = $false
    for ($i = 0; $i -lt 100 -and -not $ready; $i++) {
        Start-Sleep -Milliseconds 50
        $tmp = $null
        if ($state.TryGetValue('Ready', [ref]$tmp) -and $tmp) {
            $ready = $true
        }
    }
    if (-not $ready) {
        Write-Warning '[Toast] 等待 Toast 线程启动超时'
    }
}

function Show-Chat2CLIToast {
    param(
        [string]$Message = "Chat2CLI 执行完成"
    )

    Start-Chat2CLIToastThread

    $state = $script:Chat2CLIToastState
    if ($null -eq $state) {
        return
    }

    # 只写入命令和消息，由 Runspace 内的 DispatcherTimer 轮询消费，
    # 主线程完全不被 WPF 消息循环阻塞。
    $state['Message'] = $Message
    $state['Command'] = 'show'
}

function Update-Chat2CLIToast {
    param([string]$Message)

    $state = $script:Chat2CLIToastState
    if ($null -eq $state) {
        return
    }

    $state['Message'] = $Message
    $state['Command'] = 'update'
}

function Hide-Chat2CLIToast {
    $state = $script:Chat2CLIToastState
    if ($null -eq $state) {
        return
    }

    $state['Command'] = 'hide'
}

function Stop-Chat2CLIToastThread {
    $state = $script:Chat2CLIToastState
    if ($null -eq $state) {
        return
    }

    # 通知 Runspace 停止并等待其退出
    $state['Command'] = 'stop'
    Start-Sleep -Milliseconds 300

    $async = $null
    if ($state.TryGetValue('AsyncResult', [ref]$async) -and $null -ne $async) {
        if ($async.AsyncWaitHandle.WaitOne(2000)) {
            $ps = $null
            if ($state.TryGetValue('PowerShell', [ref]$ps) -and $null -ne $ps) {
                try {
                    $ps.EndInvoke($async) | Out-Null
                }
                catch {
                    # Runspace 关闭时可能抛出异常，忽略即可
                }
            }
        }
        else {
            # 超时：强制停止管道
            $ps = $null
            if ($state.TryGetValue('PowerShell', [ref]$ps) -and $null -ne $ps) {
                try {
                    $ps.Stop() | Out-Null
                }
                catch {
                    # 管道可能已经结束，忽略即可
                }
            }
        }
    }

    $psToDispose = $null
    if ($state.TryGetValue('PowerShell', [ref]$psToDispose) -and $null -ne $psToDispose) {
        try { $psToDispose.Dispose() } catch { }
    }

    $rsToDispose = $null
    if ($state.TryGetValue('Runspace', [ref]$rsToDispose) -and $null -ne $rsToDispose) {
        try { $rsToDispose.Dispose() } catch { }
    }

    $script:Chat2CLIToastState = $null
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
                # 结果写入剪贴板后立即读回，确认占位符已被覆盖。
                # 快速命令的结果写入可能尚未生效，占位符仍留在剪贴板，
                # 导致主循环误判已处理、剪贴板永远停在"处理中"。
                $writeVerified = $false
                for ($writeAttempt = 0; $writeAttempt -lt 3 -and -not $writeVerified; $writeAttempt++) {
                    Set-Chat2CLIClipboard $output
                    Start-Sleep -Milliseconds 50
                    $clipboardAfterWrite = Get-Chat2CLIClipboardText
                    # 读回内容不再是占位符即认为写入成功；是占位符则重试
                    $placeholderPid = Get-Chat2CLIPlaceholderPid -ClipboardText $clipboardAfterWrite
                    if ($null -eq $placeholderPid) {
                        $writeVerified = $true
                    }
                }

                if (-not $writeVerified) {
                    throw "chat2cli 结果写入剪贴板失败：多次尝试后占位符仍未被覆盖"
                }
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

        $otherPid = Get-Chat2CLIPlaceholderPid -ClipboardText $ClipboardText
        if ($null -eq $otherPid) {
            return $false
        }

        # 如果是其他进程（不是当前进程），则存在冲突
        return $otherPid -ne $currentPid
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
        Stop-Chat2CLIToastThread
    }
}


