function Send-Notification {
    <#
    .SYNOPSIS
        发送 Windows 桌面通知，可选通过 Gotify 发送手机通知。
    
    .DESCRIPTION
        发送 Windows 桌面通知。如果环境变量 GOTIFY_BASE_URL 和 GOTIFY_TOKEN 存在，
        则还会通过 Gotify API 发送手机通知。
    
    .PARAMETER Title
        通知标题。
    
    .PARAMETER Message
        通知内容。
    
    .PARAMETER Priority
        通知优先级 (0-10)，默认为 5。仅适用于 Gotify。
    
    .EXAMPLE
        Send-Notification -Title "任务完成" -Message "备份任务已成功完成"
    
    .EXAMPLE
        Send-Notification -Title "警告" -Message "磁盘空间不足" -Priority 8
    #>
    
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        
        [Parameter(Mandatory = $true)]
        [string]$Message,
        
        [Parameter(Mandatory = $false)]
        [int]$Priority = 5
    )
    
    # 发送 Windows 桌面通知
    try {
        Add-Type -AssemblyName System.Windows.Forms
        
        $notifyIcon = New-Object System.Windows.Forms.NotifyIcon
        $notifyIcon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon((Get-Command powershell).Path)
        $notifyIcon.BalloonTipIcon = 'Info'
        $notifyIcon.BalloonTipTitle = $Title
        $notifyIcon.BalloonTipText = $Message
        $notifyIcon.Visible = $true
        $notifyIcon.ShowBalloonTip(5000)
    }
    catch {
        Write-Warning "无法发送 Windows 桌面通知: $_"
    }
    
    # 检查是否配置了 Gotify
    $gotifyBaseUrl = $env:GOTIFY_BASE_URL
    $gotifyToken = $env:GOTIFY_TOKEN
    
    if ($gotifyBaseUrl -and $gotifyToken) {
        try {
            $url = "$gotifyBaseUrl/message"
            $body = @{
                message  = $Message
                title    = $Title
                priority = $Priority
            } | ConvertTo-Json
            
            $headers = @{
                "Content-Type" = "application/json"
                "X-Gotify-Key" = $gotifyToken
            }
            
            Invoke-RestMethod -Uri $url -Method Post -Body $body -Headers $headers -ErrorAction Stop | Out-Null
        }
        catch {
            Write-Warning "无法发送 Gotify 通知: $_"
        }
    }
}
