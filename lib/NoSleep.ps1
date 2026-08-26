# 脚本用途：进程级防休眠开关。
# 通过 Power Request API（PowerCreateRequest/PowerSetRequest）持有系统必需请求阻止空闲休眠，
# 原因字符串（含时间与进程号）会显示在 powercfg /requests 输出中，可与其他请求区分。
# 关键特性：请求句柄是进程级资源——无论正常退出、崩溃还是被强杀，
# 内核都会随进程结束自动关闭句柄并释放请求，无需任何退出清理钩子。
# 与 PowerToys Awake 并行无冲突：多个电源请求互相叠加，任一方释放不影响另一方。

#region serve-web 进程链辅助

function Add-NoSleepNativeSupport {
    # PowerShell 的 Process.Parent 在部分场景返回 null（如中间进程已退出），
    # 这里惰性编译辅助类型，用 NtQueryInformationProcess 直读内核记录的继承父 PID
    if (-not ('NoSleep.Vx73Qa.NativeParent' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace NoSleep.Vx73Qa
{
    public static class NativeParent
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_BASIC_INFORMATION
        {
            public IntPtr Reserved1;
            public IntPtr PebBaseAddress;
            public IntPtr Reserved2_0;
            public IntPtr Reserved2_1;
            public IntPtr UniqueProcessId;
            public IntPtr InheritedFromUniqueProcessId;
        }

        [DllImport("ntdll.dll")]
        private static extern int NtQueryInformationProcess(
            IntPtr hProcess, int pic, ref PROCESS_BASIC_INFORMATION pbi, int cb, out int pSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint access, bool inherit, int pid);

        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);

        // 返回继承父 PID；查询失败（进程已退出等）返回 -1
        // 0x1000 = PROCESS_QUERY_LIMITED_INFORMATION，同用户非提权进程即可查询
        public static int Get(int pid)
        {
            var h = OpenProcess(0x1000, false, pid);
            if (h == IntPtr.Zero) { return -1; }
            try
            {
                var pbi = new PROCESS_BASIC_INFORMATION();
                int size;
                int status = NtQueryInformationProcess(h, 0, ref pbi, Marshal.SizeOf(pbi), out size);
                return status == 0 ? pbi.InheritedFromUniqueProcessId.ToInt32() : -1;
            }
            finally { CloseHandle(h); }
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf, int size, out int read);

        // 读取目标进程完整命令行（PEB → RTL_USER_PROCESS_PARAMETERS.CommandLine，x64 偏移）
        // 用于识别 extensionHost 等 bootstrap-fork 子进程；失败返回 null
        public static string GetCommandLine(int pid)
        {
            // PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
            var h = OpenProcess(0x1000 | 0x0010, false, pid);
            if (h == IntPtr.Zero) { return null; }
            try
            {
                var pbi = new PROCESS_BASIC_INFORMATION();
                int size;
                if (NtQueryInformationProcess(h, 0, ref pbi, Marshal.SizeOf(pbi), out size) != 0) { return null; }

                var buf = new byte[8];
                int read;
                if (!ReadProcessMemory(h, (IntPtr)((long)pbi.PebBaseAddress + 0x20), buf, 8, out read)) { return null; }
                var pp = (IntPtr)BitConverter.ToInt64(buf, 0);

                // UNICODE_STRING{len,max,ptr} 位于 ProcessParameters + 0x70
                if (!ReadProcessMemory(h, (IntPtr)((long)pp + 0x70), buf, 8, out read)) { return null; }
                int len = BitConverter.ToUInt16(buf, 0);
                if (len <= 0 || len > 8000) { return ""; }
                if (!ReadProcessMemory(h, (IntPtr)((long)pp + 0x78), buf, 8, out read)) { return null; }
                var strPtr = (IntPtr)BitConverter.ToInt64(buf, 0);

                var strBuf = new byte[len];
                if (!ReadProcessMemory(h, strPtr, strBuf, len, out read)) { return null; }
                return System.Text.Encoding.Unicode.GetString(strBuf);
            }
            finally { CloseHandle(h); }
        }
    }
}
'@
    }
}

# 判断指定 PID 是否由 serve-web 服务端派生（父链命中 serve-web node 即是）
function Test-ServeWebDescendant {
    param([int]$ProcId)

    Add-NoSleepNativeSupport

    $id = $ProcId
    foreach ($i in 1..15) {
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $proc) { return $false }

        # 桌面版 VSCode 的终端祖先进程（Code.exe / Code - Insiders.exe）
        if ($proc.ProcessName -like 'Code*') { return $false }

        # serve-web 服务端固定布局：~\.vscode\cli\serve-web\<commit>\node.exe
        # 不能宽泛匹配 ~\.vscode\，桌面版扩展也安装在该目录下会造成误判
        if ($proc.ProcessName -eq 'node' -and $proc.Path -like '*\.vscode\cli\serve-web\*') {
            return $true
        }

        $parentPid = [NoSleep.Vx73Qa.NativeParent]::Get($id)
        if ($parentPid -le 0) { return $false }
        $id = $parentPid
    }
    return $false
}

#endregion

#region 扩展宿主会话判定

function Get-NoSleepAliveExthostStarts {
    <#
    .SYNOPSIS
        返回当前存活的 serve-web 扩展宿主进程启动时间数组（浏览器连接的活体标志）。
    #>
    Add-NoSleepNativeSupport
    Get-Process node -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like '*\.vscode\cli\serve-web\*' -and
        [NoSleep.Vx73Qa.NativeParent]::GetCommandLine($_.Id) -match 'extensionHost'
    } | ForEach-Object { $_.StartTime }
}

function Test-NoSleepDetached {
    <#
    .SYNOPSIS
        判断本终端是否已被其所属浏览器会话遗弃。
    .NOTES
        判据：最早存活的扩展宿主都晚于本进程出生时间。
        多窗口/多工作区场景下，只要还有任一窗口可能包含本终端就不算脱离，
        因此必须用“最早”而非“存在更晚”——否则会误杀其他窗口正在使用的终端。
    #>
    param(
        [datetime]$Birth,
        [datetime[]]$AliveStarts
    )
    if (-not $AliveStarts -or $AliveStarts.Count -eq 0) { return $false }
    $earliest = ($AliveStarts | Measure-Object -Minimum).Minimum
    return $earliest -gt $Birth
}

#endregion

#region serve-web 遗留终端清理

function Get-ServeWebShell {
    <#
    .SYNOPSIS
        列出所有由 serve-web 服务端派生的终端 pwsh 进程，并判定其所属会话状态。
    .NOTES
        会话状态判据：扩展宿主（--type=extensionHost）是浏览器连接的活体标志，
        每次连接都会拉起全新实例、断开时退出。
        - 浏览器已断开：所有终端必然为遗留
        - 浏览器连接中：晚于最早存活扩展宿主启动时间的终端在当前窗口内；
          更早的为历史残留（依赖“关闭后复活不发生”的现状，清理前请对照列表）
    #>
    Add-NoSleepNativeSupport
    $now = Get-Date

    $exthostStarts = @(Get-NoSleepAliveExthostStarts)

    $browserConnected = $exthostStarts.Count -gt 0
    # 取最早存活的扩展宿主时间做保守判断：多窗口时宁可漏判也不误杀
    $windowStart = if ($browserConnected) { ($exthostStarts | Measure-Object -Minimum).Minimum } else { $null }

    Get-Process pwsh, powershell -ErrorAction SilentlyContinue | ForEach-Object {
        if (Test-ServeWebDescendant -ProcId $_.Id) {
            $isCurrent = $_.Id -eq $PID
            $state = if ($isCurrent) { '本会话(跳过)' }
                     elseif (-not $browserConnected) { '遗留(浏览器已断开)' }
                     elseif ($_.StartTime -ge $windowStart) { '窗口使用中' }
                     else { '疑似遗留' }
            [PSCustomObject]@{
                PID      = $_.Id
                启动时间 = $_.StartTime.ToString('MM-dd HH:mm:ss')
                存活分钟 = [math]::Round(($now - $_.StartTime).TotalMinutes)
                状态     = $state
            }
        }
    }
}

function Stop-ServeWebShell {
    <#
    .SYNOPSIS
        关闭 serve-web 派生的遗留终端进程，释放其持有的防休眠请求。
    .EXAMPLE
        Stop-ServeWebShell              # 清理“遗留”终端，交互确认
        Stop-ServeWebShell -Force       # 跳过确认
        Stop-ServeWebShell -All         # 连“窗口使用中”的一起清（慎用）
        Stop-ServeWebShell -Id 12345    # 指定 PID
    #>
    param(
        # 只处理指定 PID；缺省按状态筛选
        [int[]]$Id,

        # 跳过交互确认（用于脚本化调用）
        [switch]$Force,

        # 连同“窗口使用中”的终端一起清理（默认只清理遗留项）
        [switch]$All
    )

    Add-NoSleepNativeSupport

    $shells = @(Get-ServeWebShell | Where-Object { $_.状态 -ne '本会话(跳过)' })
    $targets = if ($Id) {
        @($shells | Where-Object { $_.PID -in $Id })
    }
    elseif ($All) {
        $shells
    }
    else {
        @($shells | Where-Object { $_.状态 -like '遗留*' -or $_.状态 -eq '疑似遗留' })
    }

    if (-not $targets) {
        Write-Host '没有需要清理的 serve-web 遗留终端'
        return
    }

    $targets | Format-Table PID, 启动时间, 存活分钟, 状态 -AutoSize

    if (-not $Force) {
        $answer = Read-Host "将强制终止以上 $($targets.Count) 个进程（等效于手动关闭这些终端），确认? (y/N)"
        if ($answer -ne 'y') {
            Write-Host '已取消'
            return
        }
    }

    foreach ($t in $targets) {
        try {
            Stop-Process -Id $t.PID -Force -ErrorAction Stop
            Write-Host "✅ 已终止 $($t.PID)"
        }
        catch {
            Write-Warning "终止 $($t.PID) 失败: $_"
        }
    }
}

#endregion

#region 遗弃终端自杀看门狗

function Enable-NoSleepWatchdog {
    <#
    .SYNOPSIS
        武装本终端的自杀看门狗：所属浏览器会话被取代且闲置超时后自动退出。
    .NOTES
        - 仅在 serve-web 会话中生效；NO_SLEEP_WATCHDOG_OFF=1 可整体禁用
        - 评估通过引擎事件执行，天然只在管道空闲（无命令运行）时发生，
          不会中断正在执行的构建等长任务
        - 脱离判据见 Test-NoSleepDetached：最早存活扩展宿主晚于本进程出生时间
        - 参数可用环境变量覆盖：NO_SLEEP_WATCHDOG_IDLE / NO_SLEEP_WATCHDOG_DETACH（分钟）
    #>
    param(
        [int]$IdleMinutes = $(if ($v = $env:NO_SLEEP_WATCHDOG_IDLE) { [int]$v } else { 20 }),
        [int]$DetachGraceMinutes = $(if ($v = $env:NO_SLEEP_WATCHDOG_DETACH) { [int]$v } else { 10 })
    )

    if ($env:NO_SLEEP_WATCHDOG_OFF -eq '1') { return }
    if (-not (Test-IsServeWebSession)) { return }
    if ($global:__NS_WatchdogArmed) { return } # 幂等：重复 dot-source 不叠加

    Add-NoSleepNativeSupport

    # 出生基准用进程启动时间（稳定），活跃基准初始化为武装时刻
    $global:__NS_Birth = (Get-Process -Id $PID).StartTime
    if (-not $global:__NS_LastActive) { $global:__NS_LastActive = [datetime]::Now }
    $global:__NS_IdleMinutes = $IdleMinutes
    $global:__NS_DetachGraceMinutes = $DetachGraceMinutes

    # 包装 prompt 刷新活跃戳（链式保留原有提示符；防重复包装）
    if (-not $global:__NS_PromptWrapped) {
        $global:__NS_PreviousPrompt = $function:prompt
        $global:__NS_PromptWrapped = $true
        function global:prompt {
            $global:__NS_LastActive = [datetime]::Now
            if ($global:__NS_PreviousPrompt) {
                & $global:__NS_PreviousPrompt
            }
            else {
                "PS $($executionContext.SessionState.Path.CurrentLocation)> "
            }
        }
    }

    $timer = [System.Timers.Timer]::new(60000)
    $timer.AutoReset = $true
    Register-ObjectEvent -InputObject $timer -EventName Elapsed -SourceIdentifier 'NoSleepWatchdog' -Action {
        if ($env:NO_SLEEP_WATCHDOG_OFF -eq '1') { return }

        $alive = @(Get-NoSleepAliveExthostStarts)
        if (Test-NoSleepDetached -Birth $global:__NS_Birth -AliveStarts $alive) {
            # 首次判定脱离时开始计时，持续满足才动手（防网络闪断/刷新抖动）
            if (-not $global:__NS_DetachedSince) {
                $global:__NS_DetachedSince = [datetime]::Now
                return
            }
            $detachedFor = ([datetime]::Now - $global:__NS_DetachedSince).TotalMinutes
            $idleFor = ([datetime]::Now - $global:__NS_LastActive).TotalMinutes
            if ($detachedFor -ge $global:__NS_DetachGraceMinutes -and $idleFor -ge $global:__NS_IdleMinutes) {
                Write-Host "`n[NoSleepWatchdog] 所属浏览器会话已结束且闲置超过 $($global:__NS_IdleMinutes) 分钟，自动关闭本终端。" -ForegroundColor DarkGray
                try {
                    $Host.SetShouldExit(0)
                }
                catch {
                    Stop-Process -Id $PID -Force # 兜底：优雅路径不可用时直接自终
                }
            }
        }
        else {
            $global:__NS_DetachedSince = $null
        }
    } | Out-Null

    $timer.Start()
    $global:__NS_WatchdogTimer = $timer # 持引用防 GC
    $global:__NS_WatchdogArmed = $true
}

#endregion

function Enable-NoSleep {
    <#
    .SYNOPSIS
        阻止系统空闲休眠，直到调用 Disable-NoSleep 或当前 pwsh 进程结束。
    .NOTES
        不能阻止电源按钮、开始菜单手动睡眠、低电量强制措施等主动睡眠，属于安全兜底。
    #>
    param(
        # 同时保持屏幕常亮（默认仅保持系统唤醒，屏幕可正常熄灭）
        [switch]$Display,

        # 显示在 powercfg /requests 中的原因前缀；默认为“pwsh 防休眠”
        [string]$Reason
    )

    # Add-Type 对同名类型重复编译会报错，惰性编译前先检查类型是否已加载
    if (-not ('NoSleep.Vx73Qa.PowerRequestHolder' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

// 命名空间带固定随机后缀，避免与其他脚本可能编译的同名 NoSleep 类型冲突
namespace NoSleep.Vx73Qa
{
    public static class PowerRequestHolder
    {
        private const int PowerRequestDisplayRequired = 0;
        private const int PowerRequestSystemRequired = 1;
        private const uint ReasonContextSimple = 0x1u;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct REASON_CONTEXT
        {
            public uint Version;
            public uint Flags;
            public string Reason; // SIMPLE 模式下为原因字符串（官方结构中与 Detailed 字段互为联合）
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr PowerCreateRequest(ref REASON_CONTEXT context);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool PowerSetRequest(IntPtr handle, int requestType);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool PowerClearRequest(IntPtr handle, int requestType);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);

        // 请求句柄进程级有效：持有期间阻止空闲睡眠，进程退出时内核自动释放
        private static IntPtr _handle = IntPtr.Zero;
        private static bool _displaySet;

        public static bool IsActive
        {
            get { return _handle != IntPtr.Zero; }
        }

        public static void Start(string reason, bool displayRequired)
        {
            if (IsActive) { return; } // 幂等：本进程只持有一份请求

            var context = new REASON_CONTEXT
            {
                Version = 0,
                Flags = ReasonContextSimple,
                Reason = reason,
            };
            _handle = PowerCreateRequest(ref context);
            if (_handle == IntPtr.Zero)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "PowerCreateRequest 调用失败");
            }

            try
            {
                SetRequest(PowerRequestSystemRequired);
                _displaySet = false;
                if (displayRequired)
                {
                    SetRequest(PowerRequestDisplayRequired);
                    _displaySet = true;
                }
            }
            catch
            {
                Stop(); // 失败时回收已创建的请求，不留半持状态
                throw;
            }
        }

        private static void SetRequest(int requestType)
        {
            if (!PowerSetRequest(_handle, requestType))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "PowerSetRequest 调用失败");
            }
        }

        public static void Stop()
        {
            if (_handle == IntPtr.Zero) { return; }
            // Clear 的返回值无需检查：随后关闭句柄本身就会释放该句柄的全部请求
            PowerClearRequest(_handle, PowerRequestSystemRequired);
            if (_displaySet) { PowerClearRequest(_handle, PowerRequestDisplayRequired); }
            CloseHandle(_handle);
            _handle = IntPtr.Zero;
            _displaySet = false;
        }
    }
}
'@
    }

    # 原因统一附带时间与进程号，便于在 powercfg /requests 中区分多个请求的来源和发起时刻
    $timeStamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    if ($Reason) {
        $Reason = "$Reason @ $timeStamp (pid $PID)"
    }
    else {
        $Reason = "pwsh 防休眠 @ $timeStamp (pid $PID)"
    }

    [NoSleep.Vx73Qa.PowerRequestHolder]::Start($Reason, $Display.IsPresent)
}

function Disable-NoSleep {
    <#
    .SYNOPSIS
        解除当前 pwsh 进程持有的防休眠请求（不影响其他终端的请求和 PowerToys Awake）。
    #>
    if (-not ('NoSleep.Vx73Qa.PowerRequestHolder' -as [type])) { return }
    [NoSleep.Vx73Qa.PowerRequestHolder]::Stop()
}

function Get-NoSleepStatus {
    <#
    .SYNOPSIS
        返回当前 pwsh 进程是否正在持有防休眠请求。
    #>
    return ('NoSleep.Vx73Qa.PowerRequestHolder' -as [type]) -and [NoSleep.Vx73Qa.PowerRequestHolder]::IsActive
}

function Test-IsServeWebSession {
    <#
    .SYNOPSIS
        判断当前 pwsh 是否处于 code serve-web（浏览器版 VSCode）派生的终端中。
    .NOTES
        VSCode 对所有集成终端（桌面端/网页端/远程）注入相同的环境变量，
        无法靠 TERM_PROGRAM 等区分来源，因此沿父进程链判定：
        命中 serve-web 服务端 node 进程返回 True；命中桌面版 Code 进程返回 False。
        若服务端是从桌面版终端里启动的，其浏览器会话的终端仍会先命中服务端节点，
        正确地归类为网页端（此时用户确实在远程访问）。
    #>
    # 快速路径：VSCode 向所有集成终端注入相同的 TERM_PROGRAM，
    # 先用它零成本排除非 VSCode 环境（控制台/计划任务/agent 等），避免进程链遍历；
    # 桌面端与网页端的真正区分靠父进程链判定（Test-ServeWebDescendant）
    if ($env:TERM_PROGRAM -ne 'vscode') { return $false }

    return Test-ServeWebDescendant -ProcId $PID
}
