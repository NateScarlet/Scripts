
<#
.SYNOPSIS
    恢复卡死的 Docker Desktop（WSL2 后端）。
.DESCRIPTION

    针对已知的 WSL2 9P/drvfs 缺陷导致的 docker-desktop 发行版崩溃循环：
    发行版每 20-25 分钟崩溃一次，VM 内 dockerd 永远起不来，Windows 侧 backend
    无限等待 init control API，表现为 docker CLI 无响应、UI 卡在 "Starting the Docker Engine"。

    单独重启 Docker Desktop 无效（backend 会连回同一个坏 VM），
    单独 wsl --shutdown 也常常无效（Docker 的 watchdog 会立即把 VM 拉起来）。
    因此本脚本的顺序是：先杀 Docker 用户态进程切断 watchdog，再 wsl --shutdown。

    已知 issue：
      microsoft/WSL#41631  本机复现记录（含 dmesg 证据）
      https://github.com/microsoft/WSL/issues/41631
      microsoft/WSL#41484  p9io.cpp:258 (AcceptAsync) + drvfs automount
      microsoft/WSL#41191  Kernel BUG at fs/namei.c:844 after 9P channel disruption

    注意：wsl --shutdown 会关闭整个 WSL2 虚拟机，所有发行版（含 Ubuntu）都会被停止，
    下次访问时自动重启，不会丢失数据。
.PARAMETER Force
    跳过引擎响应检测，直接执行恢复流程。
.PARAMETER TimeoutSeconds
    等待引擎恢复的最长秒数，默认 180。超时后脚本报错退出。
.PARAMETER DockerDesktopExe
    Docker Desktop 可执行文件路径，默认标准安装位置。
.EXAMPLE
    .\Reset-DockerDesktop.ps1
    检测到引擎无响应时执行恢复。
.EXAMPLE
    .\Reset-DockerDesktop.ps1 -Force
    无条件执行恢复流程。
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [int]$TimeoutSeconds = 180,
    [string]$DockerDesktopExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
)

$ErrorActionPreference = 'Stop'

# #region 常量
# 需要终止的用户态进程。
# 不含 com.docker.service：那是 Windows 服务，负责与 VM 通信，
# 重启 Docker Desktop 时会复用，无需也无法用 Stop-Process 管理。
$DockerUserProcessNames = @(
    'Docker Desktop',
    'com.docker.backend',
    'com.docker.build',
    'com.docker.dev-envs',
    'com.docker.diagnostic',
    'docker-sandbox'
)
$ProbeTimeoutSeconds = 10
# #endregion

# #region 函数

# 探测 Docker 引擎是否在指定时间内响应。
# 用 Start-Job 是因为 docker CLI 自身没有超时开关，卡死时必须能从外部中断。
function Test-DockerEngineResponsive {
    param([int]$TimeoutSeconds)

    $job = Start-Job -ScriptBlock {
        docker version --format '{{.Server.Version}}' 2>&1 | Out-String
    }
    try {
        if (-not (Wait-Job $job -Timeout $TimeoutSeconds)) {
            return $false
        }
        $out = (Receive-Job $job) -join "`n"
        return $out.Trim() -match '^\d+\.\d+'
    } finally {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

# 终止所有匹配的 Docker 用户态进程，返回哪些成功、哪些失败。
function Stop-DockerUserProcesses {
    param([string[]]$Names)

    $killed = [System.Collections.Generic.List[string]]::new()
    $failed = [System.Collections.Generic.List[string]]::new()
    $targets = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $Names -contains $_.ProcessName }

    foreach ($proc in $targets) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            $killed.Add("$($proc.ProcessName) (PID $($proc.Id))")
        } catch {
            $failed.Add("$($proc.ProcessName) (PID $($proc.Id)): $($_.Exception.Message)")
        }
    }

    [PSCustomObject]@{ Killed = $killed; Failed = $failed }
}

# 重新枚举，检查是否还有残留。残留会让后续 wsl --shutdown 无效
# （watchdog 会立刻把 VM 拉起来），因此必须中止。
function Get-RemainingDockerProcesses {
    param([string[]]$Names)

    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $Names -contains $_.ProcessName }
}

# #endregion

# #region 主流程
Write-Host "=== Docker Desktop 恢复流程开始 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Cyan

# 1. 检测引擎是否真的卡死
if (-not $Force) {
    Write-Host "[1/5] 检测 Docker 引擎响应（最多 $ProbeTimeoutSeconds 秒）..."
    if (Test-DockerEngineResponsive -TimeoutSeconds $ProbeTimeoutSeconds) {
        Write-Warning 'Docker 引擎正常响应，无需恢复。若要强制执行请加 -Force。'
        return
    }
    Write-Host '      引擎无响应，继续。' -ForegroundColor Yellow
} else {
    Write-Host '[1/5] 已指定 -Force，跳过检测。'
}

# 2. 终止 Docker 用户态进程（切断 watchdog）
Write-Host '[2/5] 终止 Docker Desktop 用户态进程...'
$result = Stop-DockerUserProcesses -Names $DockerUserProcessNames
foreach ($k in $result.Killed) { Write-Host "      已终止: $k" }
foreach ($f in $result.Failed) { Write-Warning "      终止失败: $f" }

Start-Sleep -Seconds 3

$remaining = Get-RemainingDockerProcesses -Names $DockerUserProcessNames
if ($remaining) {
    $desc = ($remaining | ForEach-Object { "$($_.ProcessName) (PID $($_.Id))" }) -join ', '
    throw "仍有 Docker 进程存活: $desc。请手动结束它们后重试。"
}
Write-Host '      所有 Docker 用户态进程已终止。'

# 3. 关闭 WSL 虚拟机
Write-Host '[3/5] 关闭 WSL 虚拟机（所有发行版将被停止，下次访问自动重启）...'
wsl.exe --shutdown
Start-Sleep -Seconds 4
Write-Host (wsl.exe --list --verbose 2>&1 | Out-String).TrimEnd()

# 4. 启动 Docker Desktop
Write-Host '[4/5] 启动 Docker Desktop...'
if (-not (Test-Path $DockerDesktopExe)) {
    throw "找不到 Docker Desktop: $DockerDesktopExe。可用 -DockerDesktopExe 指定其他路径。"
}
Start-Process $DockerDesktopExe
Write-Host "      已启动: $DockerDesktopExe"

# 5. 等待引擎恢复
Write-Host "[5/5] 等待引擎恢复（最长 $TimeoutSeconds 秒）..."
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$recovered = $false
while ((Get-Date) -lt $deadline) {
    if (Test-DockerEngineResponsive -TimeoutSeconds 15) {
        $recovered = $true
        break
    }
    Write-Host "      [$((Get-Date).ToString('HH:mm:ss'))] 尚未就绪..."
    Start-Sleep -Seconds 5
}

if (-not $recovered) {
    throw "等待 $TimeoutSeconds 秒后引擎仍未恢复。请查看日志: $env:LOCALAPPDATA\Docker\log\host\"
}

Write-Host "=== 恢复成功 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Green
docker version --format 'Server: {{.Server.Version}}'
# #endregion
