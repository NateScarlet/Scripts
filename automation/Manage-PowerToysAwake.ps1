# 脚本用途：根据当前会话状态自动管理 PowerToys Awake
# 1. 活跃的远程会话 (RDP-Tcp#n) -> 启用防睡眠 (Mode 1)
# 2. 本地会话或已断开的会话 -> 禁用防睡眠 (Mode 0)

$awakePath = "$env:LOCALAPPDATA\PowerToys\PowerToys.Awake.exe"
if (-not (Test-Path $awakePath)) {
    $awakePath = "C:\Program Files\PowerToys\PowerToys.Awake.exe"
}

if (-not (Test-Path $awakePath)) { exit 0 }

# 核心逻辑：只有当前会话是活跃且为远程 RDP 时（SESSIONNAME 包含 # 数字），才开启防睡眠。
# 断开连接时，SESSIONNAME 通常会变回 RDP-Tcp (没有编号)，此时 $isActiveRemote 为 False。
$isActiveRemote = $null -ne $env:SESSIONNAME -and $env:SESSIONNAME -match "^RDP-Tcp#\d+"
$targetMode = if ($isActiveRemote) { 1 } else { 0 }

$settingsPath = "$env:LOCALAPPDATA\Microsoft\PowerToys\Awake\settings.json"

if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
        if ($settings.properties.mode -ne $targetMode) {
            $settings.properties.mode = $targetMode
            $settings | ConvertTo-Json -Compress | Set-Content $settingsPath
            
            # 通知 Awake 应用新配置
            Start-Process -FilePath $awakePath -ArgumentList "--use-pt-config" -WindowStyle Hidden
        }
    }
    catch {
        # 静默失败
    }
}
else {
    # 如果处于活跃远程连接但没找到配置文件，尝试直接启动
    if ($isActiveRemote) {
        Start-Process -FilePath $awakePath -WindowStyle Hidden
    }
}
