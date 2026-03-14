# 脚本用途：根据当前会话状态自动管理 PowerToys Awake
# 1. 活跃的远程会话 (Active RDP) -> 启用防睡眠
# 2. 已断开的远程会话或本地会话 -> 禁用防睡眠 (Mode 0)

$awakePath = "$env:LOCALAPPDATA\PowerToys\PowerToys.Awake.exe"
if (-not (Test-Path $awakePath)) {
    $awakePath = "C:\Program Files\PowerToys\PowerToys.Awake.exe"
}
if (-not (Test-Path $awakePath)) { exit 0 }

# 获取当前进程的 Session ID
$currentSessionId = (Get-Process -Id $PID).SessionId

# 使用 qwinsta 获取所有会话，并锁定当前 Session ID 的那一行
# 过滤掉表头，只关注包含当前 ID 且状态为 Active 的行
$sessionLine = qwinsta $currentSessionId 2>$null | Where-Object { $_ -match "\s+$currentSessionId\s+Active" }

$isActiveRemote = $false
# 如果找到了活跃行，且会话名称（通常在行首）包含 "rdp"
if ($null -ne $sessionLine -and $sessionLine -match "(?i)rdp") {
    $isActiveRemote = $true
}

$targetMode = if ($isActiveRemote) { 1 } else { 0 }
$settingsPath = "$env:LOCALAPPDATA\Microsoft\PowerToys\Awake\settings.json"

if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
        if ($settings.properties.mode -ne $targetMode) {
            $settings.properties.mode = $targetMode
            $settings | ConvertTo-Json -Compress | Set-Content $settingsPath
            
            # 通知 Awake 应用新配置 (使用子进程静默启动)
            Start-Process -FilePath $awakePath -ArgumentList "--use-pt-config" -WindowStyle Hidden
        }
    }
    catch {
        # 静默失败
    }
}
elseif ($isActiveRemote) {
    Start-Process -FilePath $awakePath -WindowStyle Hidden
}
