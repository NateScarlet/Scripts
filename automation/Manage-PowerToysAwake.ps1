param(
    [Parameter(Mandatory = $false)]
    [bool]$IsRemote
)

# 切换至本地时保持唤醒的时间 (分钟)
$idleMinutes = 10

# 如果没有传入参数，则主动获取会话状态
if (-not $PSBoundParameters.ContainsKey('IsRemote')) {
    . "$PSScriptRoot\..\lib\Get-SessionStatus.ps1"
    $IsRemote = Get-IsRemoteSession
}

$awakePath = "$env:LOCALAPPDATA\PowerToys\PowerToys.Awake.exe"
if (-not (Test-Path $awakePath)) {
    $awakePath = "C:\Program Files\PowerToys\PowerToys.Awake.exe"
}
if (-not (Test-Path $awakePath)) { exit 0 }
$settingsPath = "$env:LOCALAPPDATA\Microsoft\PowerToys\Awake\settings.json"

if (Test-Path $settingsPath) {
    try {
        $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
        $currentMode = $settings.properties.mode
        $newExpiration = [DateTimeOffset]::Now.AddMinutes($idleMinutes)
        $forceUpdate = $false

        if ($IsRemote) {
            $targetMode = 1
        }
        else {
            # 目标为计时模式
            $targetMode = 2
            
            # 解析当前配置中的过期时间
            $currentExpiration = [DateTimeOffset]::MinValue
            if ($settings.properties.expirationDateTime) {
                try { $currentExpiration = [DateTimeOffset]::Parse($settings.properties.expirationDateTime) } catch {}
            }

            # 逻辑：只有当我们需要从其他模式切换到计时模式，
            # 或者本脚本计算的过期时间比当前配置文件中的更晚（即延长了唤醒时间）时，才执行更新。
            # 这可以防止缩短其他脚本或用户手动在 UI 中设置的更长唤醒时间。
            if ($currentMode -ne 2 -or $newExpiration -gt $currentExpiration) {
                $settings.properties.expirationDateTime = $newExpiration.ToString("yyyy-MM-ddTHH:mm:ss.fffffffK")
                $forceUpdate = $true
            }
        }

        # 只要模式本身发生变更，或者触发了强制更新（重置计时器），则保存并通知
        if ($currentMode -ne $targetMode -or $forceUpdate) {
            $settings.properties.mode = $targetMode
            $settings | ConvertTo-Json -Compress | Set-Content $settingsPath

            # 通知 Awake 应用新配置 (使用子进程静默启动)
            # 通过覆盖 expirationDateTime 确保计时器得到物理上的重置/延长
            Start-Process -FilePath $awakePath -ArgumentList "--use-pt-config" -WindowStyle Hidden
        }
    }
    catch {
        # 静默失败
    }
}
elseif ($IsRemote) {
    Start-Process -FilePath $awakePath -WindowStyle Hidden
}
