
<#
.SYNOPSIS
    启动 Docker Desktop，并确保设置了自动重启的容器就位。
.DESCRIPTION

    Docker 的 restart 策略只在容器成功启动过之后才生效。WSL2 集成模式下，
    bind mount 由 systemd mount unit 在 Docker 引擎就绪后数十秒才完成挂载，
    而 daemon 一旦就绪就立即恢复 restart=always 的容器。此时单文件 bind mount
    的源路径尚不存在，容器在 create 阶段失败（State.Error 非空），
    restart 策略不会介入重试，容器就一直停留在 exited 状态，需要手动启动。

    已知 issue（机制同族，均未根治）：
      docker/for-win#71     容器在共享目录就绪前被重启（机制一致）
      docker/for-win#1192   --restart=always 破坏挂载
      docker/for-win#9823   单文件挂载的中转路径类型错乱（OPEN）
      docker/for-win#15001  开机后必须手动启动容器（OPEN）

    因此本脚本作为 Docker 的启动入口：先确保引擎就绪，再对启动失败的容器
    执行 docker start。只处理 RestartPolicy=always 且 State.Error 非空的容器；
    用户手动停止的容器 State.Error 为空，不会被误启动。
.PARAMETER TimeoutSeconds
    等待 Docker 引擎就绪的最长秒数，默认 300。
.PARAMETER RetryCount
    每个容器的最大启动尝试次数，默认 3。
.PARAMETER RetryIntervalSeconds
    两次尝试之间的间隔秒数，默认 15。
.PARAMETER DockerDesktopExe
    Docker Desktop 可执行文件路径。
.EXAMPLE
    .\Start-Docker.ps1
#>
[CmdletBinding()]
param(
    [int]$TimeoutSeconds = 300,
    [int]$RetryCount = 3,
    [int]$RetryIntervalSeconds = 15,
    [string]$DockerDesktopExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
)

$ErrorActionPreference = 'Stop'

# 加载通知模块
. "$PSScriptRoot/../../lib/Send-Notification.ps1"

# #region 函数

# 探测 Docker 引擎是否响应。
# docker CLI 自身没有超时开关，引擎卡死时调用会挂起，因此用作业从外部中断。
function Test-DockerEngineResponsive {
    param([int]$ProbeTimeoutSeconds = 10)

    $job = Start-Job -ScriptBlock { docker version --format '{{.Server.Version}}' 2>&1 | Out-String }
    try {
        if (-not (Wait-Job $job -Timeout $ProbeTimeoutSeconds)) {
            return $false
        }
        $out = (Receive-Job $job) -join "`n"
        return $out.Trim() -match '^\d+\.\d+'
    }
    finally {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
    }
}

# 找出"设置了自动重启但当前未运行"的容器。
# State.Error 只在启动失败时保留，用户手动 stop 的容器该字段为空，
# 因此不需要维护容器白名单。
function Get-PendingAutoStartContainers {
    $ids = @(docker ps -aq --filter 'status=exited')
    if ($ids.Count -eq 0) {
        return @()
    }

    $items = docker inspect $ids | ConvertFrom-Json
    return @($items | Where-Object {
            $_.HostConfig.RestartPolicy.Name -eq 'always' -and
            $_.State.Status -eq 'exited' -and
            -not [string]::IsNullOrWhiteSpace($_.State.Error)
        })
}

# 带重试地启动单个容器。
function Start-ContainerWithRetry {
    param(
        [string]$Name,
        [int]$MaxAttempts,
        [int]$IntervalSeconds
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        docker start $Name 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        if ($attempt -lt $MaxAttempts) {
            Write-Host "      第 $attempt 次启动失败，$IntervalSeconds 秒后重试..."
            Start-Sleep -Seconds $IntervalSeconds
        }
    }
    return $false;
}

# #endregion

# #region 主流程
Write-Host "=== Docker 启动流程 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Cyan

# 1. 确保 Docker 引擎就绪
Write-Host '[1/4] 检查 Docker 引擎...'
if (Test-DockerEngineResponsive -ProbeTimeoutSeconds 10) {
    Write-Host '      引擎已就绪。'
}
else {
    Write-Host '      引擎无响应，启动 Docker Desktop...'
    # 进程已在运行时重复启动会弹窗或无效，只等待不重复拉起。
    if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path $DockerDesktopExe)) {
            throw "找不到 Docker Desktop: $DockerDesktopExe"
        }
        Start-Process $DockerDesktopExe
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerEngineResponsive -ProbeTimeoutSeconds 15) {
            $ready = $true
            break
        }
        Write-Host "      [$((Get-Date).ToString('HH:mm:ss'))] 等待引擎就绪..."
        Start-Sleep -Seconds 5
    }
    if (-not $ready) {
        throw "等待 $TimeoutSeconds 秒后引擎仍未就绪，放弃。请查看日志: $env:LOCALAPPDATA\Docker\log\host\"
    }
    Write-Host '      引擎已就绪。'
}

# 2. 枚举需要启动的容器
Write-Host '[2/4] 检查自动启动的容器...'
$pending = @(Get-PendingAutoStartContainers)
if ($pending.Count -eq 0) {
    Write-Host '      所有自动启动的容器均已在运行。' -ForegroundColor Green
    Write-Host "=== 完成 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Green
    return
}
foreach ($c in $pending) {
    Write-Host "      - $($c.Name.TrimStart('/'))"
}

# 3. 逐个启动
Write-Host "[3/4] 启动容器（最多 $RetryCount 次尝试，间隔 $RetryIntervalSeconds 秒）..."
foreach ($c in $pending) {
    $name = $c.Name.TrimStart('/')
    Write-Host "      启动 $name ..."
    if (Start-ContainerWithRetry -Name $name -MaxAttempts $RetryCount -IntervalSeconds $RetryIntervalSeconds) {
        Write-Host "      已启动: $name" -ForegroundColor Green
    }
    else {
        Write-Warning "      启动失败: $name"
    }
}

# 4. 校验最终状态
Write-Host '[4/4] 校验结果...'
$remaining = @(Get-PendingAutoStartContainers)
if ($remaining.Count -gt 0) {
    $names = ($remaining | ForEach-Object { $_.Name.TrimStart('/') }) -join ', '
    $message = "以下容器仍未启动: $names"
    Write-Warning $message
    Send-Notification -Title 'Docker 容器启动失败' -Message $message -Priority 8
    throw $message
}

Write-Host "=== 全部容器已启动 $(Get-Date -Format 'HH:mm:ss') ===" -ForegroundColor Green
# #endregion
