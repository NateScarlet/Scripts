function Get-IsRemoteSession {
    <#
    .SYNOPSIS
        检查当前会话是否为活跃的远程桌面 (RDP) 会话。
    #>
    # 获取当前进程的 Session ID
    $currentSessionId = (Get-Process -Id $PID).SessionId

    # 使用 qwinsta 获取所有会话，并锁定当前 Session ID 的那一行
    # 过滤掉表头，只关注包含当前 ID 且状态为 Active 的行
    $sessionLine = qwinsta $currentSessionId 2>$null | Where-Object { $_ -match "\s+$currentSessionId\s+Active" }

    # 如果找到了活跃行，且会话名称（通常在行首）包含 "rdp"
    if ($null -ne $sessionLine -and $sessionLine -match "(?i)rdp") {
        return $true
    }
    return $false
}
