param(
    [Parameter(Mandatory = $false)]
    [bool]$IsRemote
)

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

$targetMode = if ($IsRemote) { 1 } else { 0 }
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
elseif ($IsRemote) {
    Start-Process -FilePath $awakePath -WindowStyle Hidden
}
