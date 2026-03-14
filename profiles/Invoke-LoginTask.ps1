# 脚本用途：在用户登录时根据会话类型自动配置 PowerToys Awake 状态
# 远程会话 (RDP) -> 保持唤醒（禁用睡眠）
# 本地会话 -> 停止 Awake（允许系统正常睡眠）

$ErrorActionPreference = "Continue" # 允许部分失败（如停止不存在的进程）

$awakePath = "$env:LOCALAPPDATA\PowerToys\PowerToys.Awake.exe"

if (-not (Test-Path $awakePath)) {
    # 尝试备选路径（如果安装在 Program Files）
    $awakePath = "C:\Program Files\PowerToys\PowerToys.Awake.exe"
}

if (-not (Test-Path $awakePath)) {
    Write-Warning "未找到 PowerToys.Awake.exe"
    exit 0
}

# 检查操作系统的环境变量确定是否为远程会话
$isRemote = $null -ne $env:SESSIONNAME -and $env:SESSIONNAME -like "RDP*"
$settingsPath = "$env:LOCALAPPDATA\Microsoft\PowerToys\Awake\settings.json"

if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
        
        if ($isRemote) {
            Write-Host "检测到远程会话 ($env:SESSIONNAME)，将 PowerToys Awake 设置为：无限期唤醒 (Mode 1)"
            $settings.properties.mode = 1
        }
        else {
            Write-Host "检测到本地会话 ($env:SESSIONNAME)，将 PowerToys Awake 设置为：待机/被动 (Mode 0)"
            $settings.properties.mode = 0
        }
        
        $settings | ConvertTo-Json -Compress | Set-Content $settingsPath
        
        # 启动或通知 Awake 应用新配置
        # 使用 --use-pt-config 告诉 Awake 从配置文件读取状态
        Start-Process -FilePath $awakePath -ArgumentList "--use-pt-config" -WindowStyle Hidden
    }
    catch {
        Write-Error "更新 Awake 配置文件失败: $_"
    }
}
else {
    Write-Warning "未找到 Awake 配置文件: $settingsPath"
    # 如果没有配置文件且不支持 --mode，通常无法通过 CLI 直接设置无限期唤醒且同时保持配置同步
    # 这里仅启动进程
    Start-Process -FilePath $awakePath -WindowStyle Hidden
}
