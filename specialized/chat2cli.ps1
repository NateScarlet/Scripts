function Invoke-Chat2CLI {
    $output = Get-Clipboard | py $PSScriptRoot/chat2cli.py
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

    $scriptPath = "$PSScriptRoot/chat2cli.py"

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
