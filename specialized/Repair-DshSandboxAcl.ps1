<#
.SYNOPSIS
    递归修复 DSH Windows 沙箱下目录的写入权限与低完整性标签。

.DESCRIPTION
    DSH 的写入沙箱以低完整性（Low integrity）运行受限进程。Windows 强制完整性
    控制（MIC）规定：低完整性进程只能写带低（或更低）标签的对象，与 DACL 无关。
    标签不具备追溯性——打标签之前就存在的目录会一直拒绝写入，直到单独给它补标签。

    本脚本遍历给定目录树，对每个目录：

      1. 读取 ACL 与强制标签；
      2. 缺少有效 WRITE_DAC 或 WRITE_OWNER 时，为当前登录用户补一条完全控制
         允许项（这是后续打标签的前提）；
      3. 标签不是低完整性时，补 (OI)(CI)Low 标签，使子项继承；
      4. 删除其他打包应用残留的允许项（S-1-15-2-*，两个已知组除外）；
      5. 重新读取并验证，记录结果。

    每处改动前都写一份恢复记录，可用 -RestoreRecord 还原。脚本不删除文件，
    不改文件内容，不改所有者。需要非受限运行：打标签需要 WRITE_OWNER，
    受限进程没有。

    本脚本不依赖 diagnose-windows-sandbox-acl skill，自行实现相同机制。

.PARAMETER Path
    要修复的根目录，递归处理。

.PARAMETER Out
    报告与恢复记录的目录。修复模式必填。

.PARAMETER Exclude
    跳过的目录名，默认是包缓存与构建产物。

.PARAMETER MaxDirectories
    单次运行最多访问的目录数，防止超大目录树变成无界遍历。

.PARAMETER DryRun
    只报告将要做什么，不改任何东西。

.PARAMETER RestoreRecord
    还原一份恢复记录，而不是修复。

.EXAMPLE
    pwsh -File Repair-DshSandboxAcl.ps1 -Path 'C:\Workspaces\scripts' -Out 'C:\Workspaces\scripts\.scratch\2026-10-31-dsh-acl-repair\tree'

.EXAMPLE
    pwsh -File Repair-DshSandboxAcl.ps1 -RestoreRecord 'C:\...\acl-backup-xxx.json'
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [string]$Out,
    [string[]]$Exclude = @('node_modules', '.venv', '__pycache__', 'build', 'dist', '.ruff_cache', '.pytest_cache', '.mypy_cache'),
    [int]$MaxDirectories = 20000,
    [switch]$DryRun,
    [string]$RestoreRecord
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 打包应用（AppContainer）的允许项会让 DSH 自己的授权过程失败；
# 以 1 或 2 结尾的两个 SID 代表全部应用，不能删除。
$PackageSidPattern = '^S-1-15-2-(?![12]$)'
$WriteDacMask = 0x40000
$WriteOwnerMask = 0x80000

$script:ReportWriter = $null
$script:ReportPath = $null

#region 报告

function Write-Report {
    param([string]$Kind, [string]$Operation, [string]$Target, [string]$Status, [string]$Reason, $Details = @{})
    $record = [ordered]@{
        kind = $Kind; operation = $Operation; path = $Target
        status = $Status; reason = $Reason; details = $Details
    }
    $json = $record | ConvertTo-Json -Depth 10 -Compress
    if ($null -ne $script:ReportWriter) {
        $script:ReportWriter.WriteLine($json)
        $script:ReportWriter.Flush()
    }
    # 报告走 Console 而不是管道，避免它变成某个函数的返回值。
    [Console]::Out.WriteLine('REPORT ' + $json)
}

function Open-ReportFile {
    param([string]$Directory)
    [System.IO.Directory]::CreateDirectory($Directory) | Out-Null
    $script:ReportPath = Join-Path $Directory ('acl-repair-{0}.jsonl' -f [guid]::NewGuid().ToString('N'))
    $stream = [System.IO.File]::Open($script:ReportPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    $script:ReportWriter = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false))
}

#endregion

#region 原生 API

function Initialize-NativeApi {
    if ('DshRepair.Native' -as [type]) { return }
    Add-Type -Namespace DshRepair -Name Native -MemberDefinition @'
// -MemberDefinition 会把片段放进类体，因此不能用 using 指令，全部写完全限定名。
[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
private static extern Microsoft.Win32.SafeHandles.SafeFileHandle CreateFileW(
  string path, uint access, uint share, System.IntPtr security, uint disposition, uint flags, System.IntPtr template);

[DllImport("advapi32.dll", CharSet = CharSet.Unicode)]
private static extern uint SetNamedSecurityInfoW(string path, int type, uint information,
  System.IntPtr owner, System.IntPtr group, byte[] dacl, System.IntPtr sacl);

// OPEN_EXISTING 不创建也不修改内容；Windows 按令牌的组、拒绝项与继承计算有效访问。
public static bool HasAccess(string path, uint access) {
  using (var handle = CreateFileW(path, access, 7, System.IntPtr.Zero, 3, 0x02200000, System.IntPtr.Zero)) {
    if (!handle.IsInvalid) { return true; }
    int error = System.Runtime.InteropServices.Marshal.GetLastWin32Error();
    if (error == 5) { return false; }
    throw new System.ComponentModel.Win32Exception(error, "access check: " + path);
  }
}

// 读当前进程令牌的完整性级别。受限沙箱进程的 WRITE_DAC 结果不可信，
// 打标签也需要受限进程没有的特权，因此必须先认出受限运行。
[DllImport("advapi32.dll", SetLastError = true)]
public static extern bool GetTokenInformation(IntPtr token, int infoClass, IntPtr info, uint length, out uint returned);
[DllImport("advapi32.dll", SetLastError = true)]
public static extern IntPtr GetSidSubAuthority(IntPtr sid, uint index);
[DllImport("advapi32.dll", SetLastError = true)]
public static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

[StructLayout(LayoutKind.Sequential)]
public struct SID_AND_ATTRIBUTES { public IntPtr Sid; public uint Attributes; }
[StructLayout(LayoutKind.Sequential)]
public struct TOKEN_MANDATORY_LABEL { public SID_AND_ATTRIBUTES Label; }

// 返回令牌完整性级别的 RID；调用方据此判断是否低于 Medium。
public static int IntegrityLevel(IntPtr token) {
  uint length;
  GetTokenInformation(token, 25, IntPtr.Zero, 0, out length);
  if (length == 0) { throw new System.ComponentModel.Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error(), "Read integrity size"); }
  IntPtr buffer = System.Runtime.InteropServices.Marshal.AllocHGlobal((int)length);
  try {
    if (!GetTokenInformation(token, 25, buffer, length, out length)) { throw new System.ComponentModel.Win32Exception(System.Runtime.InteropServices.Marshal.GetLastWin32Error(), "Read integrity level"); }
    IntPtr sid = System.Runtime.InteropServices.Marshal.PtrToStructure<TOKEN_MANDATORY_LABEL>(buffer).Label.Sid;
    byte count = System.Runtime.InteropServices.Marshal.ReadByte(GetSidSubAuthorityCount(sid));
    return System.Runtime.InteropServices.Marshal.ReadInt32(GetSidSubAuthority(sid, (uint)(count - 1)));
  } finally { System.Runtime.InteropServices.Marshal.FreeHGlobal(buffer); }
}

// 只写 DACL 与继承保护标志，从不触碰 owner、group 或 SACL。
public static void SetDacl(string path, string sddl) {
  var descriptor = new System.Security.AccessControl.RawSecurityDescriptor(sddl);
  byte[] dacl = null;
  if (descriptor.DiscretionaryAcl != null) {
    dacl = new byte[descriptor.DiscretionaryAcl.BinaryLength];
    descriptor.DiscretionaryAcl.GetBinaryForm(dacl, 0);
  }
  bool isProtected = (descriptor.ControlFlags & System.Security.AccessControl.ControlFlags.DiscretionaryAclProtected) != 0;
  uint result = SetNamedSecurityInfoW(path, 1, 4u | (isProtected ? 0x80000000u : 0x20000000u),
    System.IntPtr.Zero, System.IntPtr.Zero, dacl, System.IntPtr.Zero);
  if (result != 0) { throw new System.ComponentModel.Win32Exception((int)result, "Write DACL: " + path); }
}
'@
}

#endregion

#region 路径与安全检查

function Get-NormalizedPath {
    param([string]$Value)
    $full = [System.IO.Path]::GetFullPath($Value)
    $root = [System.IO.Path]::GetPathRoot($full)
    if ($full.Length -le $root.Length) { return $root }
    return $full.TrimEnd('\', '/')
}

function Test-DangerousRoot {
    param([string]$FullPath)
    $trimmed = (Get-NormalizedPath $FullPath).TrimEnd('\')
    if ($trimmed -match '^[A-Za-z]:$') { return 'drive root' }
    if ($trimmed -ieq ([System.IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\'))) { return 'user profile root' }
    if ($trimmed -ieq ([System.IO.Path]::GetFullPath($env:WINDIR).TrimEnd('\'))) { return 'Windows directory' }
    foreach ($entry in @(
        @{ directory = $env:LOCALAPPDATA; child = 'Packages' },
        @{ directory = $env:ProgramFiles; child = 'WindowsApps' },
        @{ directory = $env:ProgramW6432; child = 'WindowsApps' }
    )) {
        if (-not $entry.directory) { continue }
        $protected = Get-NormalizedPath (Join-Path $entry.directory $entry.child)
        if ($trimmed -ieq $protected) { return 'managed application directory' }
        if ($trimmed.StartsWith($protected.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)) { return 'managed application directory' }
    }
    return $null
}

#endregion

#region 运行环境守卫

function Get-CallerIntegrity {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $level = [DshRepair.Native]::IntegrityLevel($identity.Token)
    switch ($level) {
        0 { return 'untrusted' }
        4096 { return 'low' }
        8192 { return 'medium' }
        12288 { return 'high' }
        16384 { return 'system' }
        default { return "unknown($level)" }
    }
}

# 受限运行下读到的 WRITE_DAC 是受限令牌的有效访问结果，打标签也缺特权。
# 这种情况下修出来的结论不可信，因此直接拒绝，而不是产出一份看似成功的报告。
function Assert-Unconfined {
    $level = Get-CallerIntegrity
    if ($level -in @('untrusted', 'low')) {
        throw "当前进程完整性级别是 $level，运行在 DSH 沙箱内。修复需要非受限运行：受限令牌下权限检查结果不可信，打标签也缺少所需特权。请在沙箱外的普通终端（或把会话切到完全权限）重新运行。"
    }
    return $level
}

#endregion

#region 完整性标签

function Get-IntegrityLabel {
    param([string]$FullPath)
    # 读 SACL 需要额外特权，普通进程只能依赖 icacls 的渲染结果。
    # 输出按系统语言本地化，因此同时匹配 SID 与中英文级别名。
    $lines = @(icacls $FullPath 2>&1 | ForEach-Object { [string]$_ })
    if ($LASTEXITCODE -ne 0) { return [ordered]@{ Readable = $false; Level = 'unknown'; Text = ($lines -join ' ') } }
    $text = $lines -join "`n"
    $level = 'none'
    if ($text -match 'S-1-16-0\b|Untrusted Mandatory|不受信任') { $level = 'untrusted' }
    elseif ($text -match 'S-1-16-4096\b|Low Mandatory Level|低强制级别|低完整性') { $level = 'low' }
    elseif ($text -match 'S-1-16-8192\b|Medium Mandatory Level|中强制级别|中等完整性') { $level = 'medium' }
    elseif ($text -match 'S-1-16-12288\b|High Mandatory Level|高强制级别|高完整性') { $level = 'high' }
    elseif ($text -match 'S-1-16-16384\b|System Mandatory Level|系统强制级别') { $level = 'system' }
    return [ordered]@{ Readable = $true; Level = $level; Text = $text }
}

function Set-IntegrityLabelLevel {
    param([string]$FullPath, [string]$Level)
    $map = @{ untrusted = 'Untrusted'; low = 'Low'; medium = 'Medium'; high = 'High'; system = 'System' }
    $name = $map[$Level]
    if (-not $name) { throw "未知完整性级别: $Level" }
    $output = @(icacls $FullPath /setintegritylevel "(OI)(CI)$name" 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "icacls /setintegritylevel 失败 ($LASTEXITCODE): $($output -join ' ')" }
}

#endregion

#region DACL 工具

function Get-OwnDaclSddl {
    param([string]$Sddl)
    # 继承项跟随父项；把继承项写进备份会在还原时把它们钉成显式项，破坏继承。
    # 保留控制标志，使还原结果仍带上原来的继承保护状态。
    $flags = [regex]::Match($Sddl, '^D:([A-Z]*)').Groups[1].Value
    $aces = @([regex]::Matches($Sddl, '\([^()]*\)') | ForEach-Object { $_.Value } | Where-Object { ($_ -split ';')[1] -notmatch 'ID' })
    return 'D:{0}{1}' -f $flags, ($aces -join '')
}

function Get-AceSet {
    param([string]$Sddl)
    return @([regex]::Matches($Sddl, '\([^()]*\)') | ForEach-Object { $_.Value } | Sort-Object)
}

#endregion

#region 观察

function Get-DirectoryFacts {
    param([string]$FullPath, [string]$MeSid)
    $facts = [ordered]@{
        Path = $FullPath; Readable = $false; Error = ''
        Owner = ''; OwnerIsMe = $false; MyRights = ''
        WriteDac = $null; WriteOwner = $null
        IntegrityLabel = 'unknown'; LabelReadable = $false
        PackageAces = @()
        OwnDaclSddl = ''; Protected = $false; ObservedSddl = ''
    }
    try {
        $acl = Get-Acl -LiteralPath $FullPath
        $facts.Readable = $true
    } catch {
        $facts.Error = $_.Exception.Message
        return $facts
    }
    foreach ($rule in $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
        $sid = $rule.IdentityReference.Value
        if ($sid -match $PackageSidPattern -and $rule.AccessControlType -eq 'Allow' -and -not $rule.IsInherited) {
            $facts.PackageAces += $sid
        }
        if ($sid -eq $MeSid -and $rule.AccessControlType -eq 'Allow') {
            $facts.MyRights = ($facts.MyRights + ';' + [string]$rule.FileSystemRights).Trim(';')
        }
    }
    try {
        $facts.Owner = $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
        $facts.OwnerIsMe = ($facts.Owner -eq $MeSid)
    } catch { $facts.Owner = 'unreadable' }
    try { $facts.WriteDac = [DshRepair.Native]::HasAccess($FullPath, $WriteDacMask) }
    catch { $facts.Error = "WRITE_DAC 检查失败: $($_.Exception.Message)" }
    try { $facts.WriteOwner = [DshRepair.Native]::HasAccess($FullPath, $WriteOwnerMask) }
    catch { $facts.Error = "WRITE_OWNER 检查失败: $($_.Exception.Message)" }
    $facts.ObservedSddl = $acl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::Access)
    $facts.OwnDaclSddl = Get-OwnDaclSddl -Sddl $facts.ObservedSddl
    $facts.Protected = $acl.AreAccessRulesProtected
    $label = Get-IntegrityLabel -FullPath $FullPath
    $facts.IntegrityLabel = $label.Level
    $facts.LabelReadable = $label.Readable
    return $facts
}

function Get-DirectoryTree {
    param([string]$Root, [string[]]$Excluded, [int]$Limit)
    $directories = [System.Collections.Generic.List[string]]::new()
    $queue = [System.Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($Root)
    $visited = 0
    $skipped = 0
    $unreadable = 0
    $truncated = $false
    while ($queue.Count -gt 0) {
        if ($visited -ge $Limit) { $truncated = $true; break }
        $current = $queue.Dequeue()
        $visited++
        if ($current -ne $Root) {
            $item = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
            if ($null -eq $item) { $unreadable++; continue }
            # reparse point 指向别处，改它的 ACL 会作用到目标上，必须剪枝。
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { $skipped++; continue }
            if ($Excluded -contains $item.Name) { $skipped++; continue }
        }
        $directories.Add($current)
        try {
            foreach ($child in [System.IO.Directory]::EnumerateDirectories($current)) {
                $queue.Enqueue($child)
            }
        } catch { $unreadable++ }
    }
    return [ordered]@{
        Directories = $directories; Visited = $visited; Skipped = $skipped
        Unreadable = $unreadable; Truncated = $truncated
    }
}

#endregion

#region 恢复记录

function Restore-RecoveryRecord {
    param([string]$Record)
    $saved = Get-Content -LiteralPath $Record -Raw | ConvertFrom-Json
    if ($saved.Path -isnot [string] -or $saved.Dacl -isnot [string]) { throw '恢复记录格式不正确' }
    $danger = Test-DangerousRoot -FullPath $saved.Path
    if ($danger) { throw "拒绝恢复 $($saved.Path)：它是 $danger" }
    if (-not [DshRepair.Native]::HasAccess($saved.Path, $WriteDacMask)) { throw "恢复 $($saved.Path) 需要 WRITE_DAC" }
    [DshRepair.Native]::SetDacl($saved.Path, $saved.Dacl)
    $restoredAcl = Get-Acl -LiteralPath $saved.Path
    $actual = Get-OwnDaclSddl -Sddl $restoredAcl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::Access)
    # 继承项跟随父项，比较自有 ACE 与保护状态即可。
    $expected = Get-AceSet -Sddl $saved.Dacl
    $got = Get-AceSet -Sddl $actual
    if ((@($expected) -join "`n") -ne (@($got) -join "`n")) { throw '恢复后的 DACL 与记录不一致' }
    if ($saved.IntegrityLabel -and $saved.IntegrityLabel -notin @('low', 'unknown')) {
        # 提高完整性级别通常需要额外特权；失败时如实报告，不静默放过。
        try { Set-IntegrityLabelLevel -FullPath $saved.Path -Level $saved.IntegrityLabel }
        catch { throw "DACL 已恢复，但完整性标签恢复失败: $($_.Exception.Message)" }
    }
    Write-Report action restore_dacl $saved.Path completed 'The saved DACL and integrity label were restored.' @{ record = $Record }
}

#endregion

#region 单目录修复

function Repair-OneDirectory {
    param([string]$FullPath, [string]$MeSid, [string]$OutDirectory, [switch]$DryRun)
    $facts = Get-DirectoryFacts -FullPath $FullPath -MeSid $MeSid
    $result = [ordered]@{
        Path = $FullPath; Readable = $facts.Readable; Changes = @(); Verified = $false
        Refused = $null; Error = $null; RecoveryRecord = $null; RecoveryCommand = $null
    }
    if (-not $facts.Readable) {
        $result.Error = $facts.Error
        Write-Report observation inspect_acl $FullPath unreadable 'The ACL could not be read; no change was attempted.' @{ error = $facts.Error }
        return $result
    }
    $needDacl = (-not $facts.WriteDac) -or (-not $facts.WriteOwner)
    $needLabel = ($facts.IntegrityLabel -ne 'low')
    $needPackage = ($facts.PackageAces.Count -gt 0)
    if (-not ($needDacl -or $needLabel -or $needPackage)) {
        Write-Report observation inspect_acl $FullPath healthy 'FullControl for the current user and a Low label are both present; no package allow ACE was found.' @{}
        return $result
    }
    # 打标签需要 WRITE_OWNER；缺少它时必须先补 ACL，否则标签一定失败。
    if ($needLabel -and (-not $facts.WriteOwner) -and (-not $needDacl)) { $needDacl = $true }
    Write-Report observation inspect_acl $FullPath needs_repair 'At least one of WRITE_DAC, WRITE_OWNER or the Low label is missing, or a package allow ACE is present.' @{
        writeDac = $facts.WriteDac; writeOwner = $facts.WriteOwner; integrityLabel = $facts.IntegrityLabel
        packageAces = @($facts.PackageAces); needs = @{ dacl = $needDacl; label = $needLabel; package = $needPackage }
    }
    if ($DryRun) {
        $result.Changes = @(@{ operation = 'would_repair'; dacl = $needDacl; label = $needLabel; package = $needPackage })
        return $result
    }
    if (-not $OutDirectory) { throw '修复需要 -Out 目录用于写恢复记录' }

    # 改动前先落一份恢复记录：DACL 只保留自有 ACE，继承项跟随父项。
    $record = Join-Path $OutDirectory ('acl-backup-{0}.json' -f [guid]::NewGuid().ToString('N'))
    @{
        Path = $FullPath
        Dacl = $facts.OwnDaclSddl
        Protected = $facts.Protected
        IntegrityLabel = $facts.IntegrityLabel
        Observed = $facts.ObservedSddl
        CreatedUtc = [datetime]::UtcNow.ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath $record -Encoding utf8
    $command = "pwsh -NoProfile -File '{0}' -RestoreRecord '{1}'" -f $PSCommandPath.Replace("'", "''"), $record.Replace("'", "''")
    $result.RecoveryRecord = $record
    $result.RecoveryCommand = $command
    Write-Report decision backup $FullPath saved 'The original DACL and integrity label are recorded before any change.' @{ record = $record; command = $command }

    $attempted = @()
    try {
        if ($needDacl) {
            $attempted += 'dacl'
            $acl = Get-Acl -LiteralPath $FullPath
            $acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
                [System.Security.Principal.SecurityIdentifier]::new($MeSid),
                [System.Security.AccessControl.FileSystemRights]::FullControl,
                [System.Security.AccessControl.AccessControlType]::Allow))
            [DshRepair.Native]::SetDacl($FullPath, $acl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::Access))
            if (-not [DshRepair.Native]::HasAccess($FullPath, $WriteDacMask) -or -not [DshRepair.Native]::HasAccess($FullPath, $WriteOwnerMask)) {
                throw '补齐完全控制后 WRITE_DAC 或 WRITE_OWNER 仍不可用'
            }
            $result.Changes += @{ operation = 'grant_dacl'; sid = $MeSid }
            Write-Report action grant_dacl $FullPath completed 'A FullControl allow ACE for the current user was added; deny ACEs, owner and SACL are untouched.' @{ sid = $MeSid }
        }
        if ($needLabel) {
            $attempted += 'label'
            Set-IntegrityLabelLevel -FullPath $FullPath -Level 'low'
            $verifyLabel = Get-IntegrityLabel -FullPath $FullPath
            if ($verifyLabel.Level -ne 'low') { throw "补标签后仍读不到 Low 标签（读到 $($verifyLabel.Level)）" }
            $result.Changes += @{ operation = 'set_low_label' }
            Write-Report action set_low_label $FullPath completed 'The Low mandatory label with (OI)(CI) inheritance was applied, so existing and future children inherit it.' @{}
        }
        if ($needPackage) {
            $attempted += 'package'
            foreach ($sid in @($facts.PackageAces | Sort-Object -Unique)) {
                $output = @(icacls $FullPath /remove:g "*$sid" 2>&1)
                if ($LASTEXITCODE -ne 0) { throw "icacls 删除包允许项失败 ($LASTEXITCODE): $($output -join ' ')" }
                $result.Changes += @{ operation = 'remove_package_allow'; sid = $sid }
                Write-Report action remove_package_allow $FullPath completed 'An explicit AppContainer package allow ACE was removed; deny ACEs and other principals are untouched.' @{ sid = $sid }
            }
        }
        $result.Verified = $true
        Write-Report verification repair $FullPath verified 'Every requested change completed and was re-read successfully.' @{ changes = @($result.Changes) }
    } catch {
        $result.Error = $_.Exception.Message
        Write-Report error repair $FullPath failed 'A change failed; this directory is restored from its recovery record so the tree stays consistent.' @{ error = $_.Exception.Message; attempted = @($attempted) }
        try {
            Restore-RecoveryRecord -Record $record
            Write-Report action rollback $FullPath completed 'The recovery record for this directory was restored after the failure.' @{}
        } catch {
            Write-Report error rollback $FullPath failed 'The recovery record could not be restored; run the printed command manually.' @{ error = $_.Exception.Message; command = $command }
        }
    }
    return $result
}

#endregion

#region 入口

Initialize-NativeApi

# 还原同样要改 DACL 与标签，和修复受同一约束。
try { $callerIntegrity = Assert-Unconfined }
catch { [Console]::Error.WriteLine("REFUSED $($_.Exception.Message)"); exit 3 }

if ($RestoreRecord) {
    try {
        Restore-RecoveryRecord -Record $RestoreRecord
        Write-Output 'RESTORE=OK'
        exit 0
    } catch {
        [Console]::Error.WriteLine("RESTORE_FAILED $($_.Exception.Message)")
        exit 1
    }
}

if (-not $Path) { throw '-Path 必填（修复模式）' }
if (-not $Out) { throw '-Out 必填（修复模式）' }

$meSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if (-not $DryRun) { Open-ReportFile -Directory $Out }

Write-Report invocation repair '' started 'Walk the requested trees, then repair missing WRITE_DAC/WRITE_OWNER, missing Low labels and package allow ACEs.' @{
    paths = @($Path); out = $Out; exclude = @($Exclude); dryRun = [bool]$DryRun; callerSid = $meSid; callerIntegrity = $callerIntegrity
}

$repaired = 0
$refused = 0
$failed = 0
$scanned = 0
$totalTruncated = $false

foreach ($root in $Path) {
    $full = Get-NormalizedPath $root
    if (-not (Test-Path -LiteralPath $full)) {
        Write-Report decision repair $full refused 'The root does not exist.' @{}
        $refused++
        continue
    }
    $danger = Test-DangerousRoot -FullPath $full
    if ($danger) {
        Write-Report decision repair $full refused "Refusing to walk a $danger." @{}
        $refused++
        continue
    }
    $tree = Get-DirectoryTree -Root $full -Excluded $Exclude -Limit $MaxDirectories
    if ($tree.Truncated) { $totalTruncated = $true }
    Write-Report observation walk $full read 'The tree was enumerated without entering reparse points or excluded directories.' @{
        directories = $tree.Directories.Count; visited = $tree.Visited; skipped = $tree.Skipped
        unreadable = $tree.Unreadable; truncated = $tree.Truncated
    }
    foreach ($directory in $tree.Directories) {
        $scanned++
        $one = Repair-OneDirectory -FullPath $directory -MeSid $meSid -OutDirectory $Out -DryRun:$DryRun
        if ($one.Error) { $failed++ }
        elseif ($one.Changes.Count -gt 0) { $repaired++ }
        elseif ($one.Refused) { $refused++ }
    }
}

$recap = [ordered]@{
    scanned = $scanned; repaired = $repaired; failed = $failed; refused = $refused
    truncated = $totalTruncated; report = $script:ReportPath
}
Write-Report summary repair '' $(if ($failed -gt 0 -or $refused -gt 0) { 'partial' } else { 'completed' }) 'Completion records API execution; only a confined write can confirm the tree is usable.' $recap
if ($script:ReportWriter) { $script:ReportWriter.Dispose() }
Write-Output ('RECAP ' + ($recap | ConvertTo-Json -Depth 6 -Compress))
if ($script:ReportPath) { Write-Output ('REPORT_FILE ' + $script:ReportPath) }
if ($failed -gt 0) { exit 1 }
if ($refused -gt 0) { exit 2 }
exit 0

#endregion
