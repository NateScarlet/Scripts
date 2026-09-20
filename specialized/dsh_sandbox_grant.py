"""DSH 写入沙箱的目录放行管理工具。

用途：让 DSH 的 workspace-write 沙箱在**不切换到 danger-full-access** 的前提下，
写入工作区之外的指定目录。放行是一次性的 ACL 改动，之后所有会话都生效。

机制（对照 @deepseek-ai/dsh-sandbox-windows-acl）：

- DSH 从**规范工作区路径**确定性派生工作区能力 SID：
  sha256(工作区路径) 前 8 字节 → 两个 30 位子权威 → S-1-4-x-y
- 该 SID 被放进 WRITE_RESTRICTED 令牌的 restricting 列表，Windows 做两次
  访问检查，只有两次都通过才授予写权限
- 因此**只要给目标目录的 DACL 加一条该工作区 SID 的允许写入 ACE**，
  该目录就在所有携带此 SID 的 DSH 会话中变可写

关键约束：DSH 的 restricting 列表是写死的，runner 只接受
`--write-sid` / `--temp-write-sid` 两个由它自己派生的 SID。外部无法把自定义
SID 注入 DSH 令牌，所以放行**必须复用当前工作区的 workspaceWriteSid**。
推论：

- 放行与工作区绑定。换了工作区（cwd）就是另一个 SID，需要重新放行。
- 同一工作区的所有会话共享该放行，无法只对单个会话放行。

管理命令会改目标目录的 ACL，在沙箱内执行等于沙箱逃逸，因此检测到当前
进程已受限时直接拒绝，必须在沙箱外的普通终端运行。

用法：

    python dsh_sandbox_grant.py grant  <目录> [--workspace <工作区>]
    python dsh_sandbox_grant.py revoke <目录> [--workspace <工作区>]
    python dsh_sandbox_grant.py status <目录> [--workspace <工作区>]
    python dsh_sandbox_grant.py sid    [--workspace <工作区>]

不传 --workspace 时用当前工作目录。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys
from typing import List, Optional, Tuple

# 复用 chat2cli 沙箱已验证的 ACL 原语：DACL 读写、ACE 增删、树遍历。
# 这些是与 SID 无关的底层实现，DSH 与 chat2cli 只是喂给它们不同的 SID。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import win_write_sandbox as wws  # noqa: E402


class DshGrantError(Exception):
    """DSH 放行操作失败。"""


# ── DSH 工作区 SID 派生 ───────────────────────────────────────────


def dsh_workspace_write_sid(workspace_root: str) -> str:
    """派生 DSH 的工作区能力 SID。

    必须与 DSH 的 workspaceWriteSid 逐位一致，否则 ACE 写上去也不生效。
    DSH 的实现（lib/types-CutH1Lgc.js:855）：

        sha256(workspaceRoot, "utf8") 前 8 字节 → S-1-4-x-y

    注意两点：
    1. 哈希的是**传入的路径字符串本身**，不做小写化。调用方必须传入
       DSH 实际使用的规范路径（realpathSync.native 的结果），
       否则大小写或短名（8.3）差异会派生出另一个 SID。
    2. 与 chat2cli 的 _derive_capability_sid 算法相同，但种子不同：
       这里直接用路径，chat2cli 用 realpath 后拼 "chat2cli-grant:" 前缀。
    """
    digest = hashlib.sha256(workspace_root.encode("utf-8")).digest()
    first = struct.unpack_from("<I", digest, 0)[0] % (2**30 - 1) + 1
    second = struct.unpack_from("<I", digest, 4)[0] % (2**30 - 1) + 1
    return f"S-1-4-{first}-{second}"


def canonical_workspace(workspace_root: str) -> str:
    """把工作区路径规范化为 DSH 实际使用的那种写法。

    DSH 用 realpathSync.native 解析工作区路径（见 dsh-sandbox/roots.js 的
    canonicalPath），它会解析符号链接并归一化到真实大小写。这里用
    os.path.realpath 对齐；Python 在 Windows 上同样返回真实大小写。
    """
    return os.path.realpath(os.path.abspath(workspace_root))


def resolve_workspace(explicit: Optional[str]) -> Tuple[str, str]:
    """返回 (规范工作区路径, 工作区 SID)。"""
    raw = explicit if explicit is not None else os.getcwd()
    if not os.path.isdir(raw):
        raise DshGrantError(f"工作区目录不存在: {raw}")
    canonical = canonical_workspace(raw)
    return canonical, dsh_workspace_write_sid(canonical)


# ── 放行状态检查 ──────────────────────────────────────────────────


def _guard_not_sandboxed() -> None:
    """拒绝在 DSH 沙箱内执行管理命令。

    放行靠修改目标目录的 ACL 实现。受限令牌不含目标目录的 WRITE_DAC，
    即使能改也意味着沙箱被逃逸，因此这里无条件拒绝，要求到沙箱外执行。
    """
    try:
        sandboxed = wws.current_process_is_sandboxed()
    except wws.SandboxError as e:
        raise DshGrantError(f"无法读取当前进程令牌状态: {e}") from e
    if sandboxed:
        raise DshGrantError(
            "当前进程已运行在 DSH 写入沙箱内，拒绝执行放行管理命令。\n"
            "放行目录需要修改目标目录的 ACL，在沙箱内可改 ACL 即等于沙箱逃逸。\n"
            "请在沙箱外的普通终端（如 Windows Terminal / PowerShell）重新运行。"
        )


def _sid_already_granted(path: str, sid: str) -> bool:
    """目标目录是否已有该 SID 的允许写入 ACE（显式或继承）。

    只读检查，不修改 ACL。
    """
    sid_ptr = wws._sid_from_string(sid)
    try:
        p_sd, p_dacl = wws._read_dacl(path)
        try:
            explicit, inherited = wws._grant_ace_state(p_dacl, sid_ptr)
        finally:
            wws._kernel32.LocalFree(p_sd)
        return explicit or inherited
    finally:
        wws._kernel32.LocalFree(sid_ptr)


def _grant(path: str, sid: str) -> Tuple[bool, List[str]]:
    """给目录加一条可继承的允许写入 ACE。返回 (是否变更, 失败列表)。"""
    sid_ptr = wws._sid_from_string(sid)
    try:
        try:
            changed = wws._ensure_write_ace(path, sid_ptr)
        except wws.SandboxError as e:
            return False, [f"{path}: {e}"]
        return changed, []
    finally:
        wws._kernel32.LocalFree(sid_ptr)


def _revoke_tree(root: str, sid: str) -> wws.TreeOpResult:
    """递归撤销树中该 SID 的显式 ACE。

    父目录的显式 ACE 撤销后子项继承的 ACE 自动消失，但用户可能单独放行过
    子目录（子项上有独立显式 ACE），那些不受父项影响，必须逐项清除，
    否则撤销父目录后这些子项依然可写。
    """
    sid_ptr = wws._sid_from_string(sid)
    try:
        scanned = 0
        changed = 0
        failures: List[str] = []
        for target, _is_dir in wws._walk_tree(root):
            scanned += 1
            try:
                if wws._remove_write_ace(target, sid_ptr):
                    changed += 1
            except wws.SandboxError as e:
                failures.append(f"{target}: {e}")
        return wws.TreeOpResult(scanned, changed, failures)
    finally:
        wws._kernel32.LocalFree(sid_ptr)


# ── 子命令 ────────────────────────────────────────────────────────


def cmd_sid(workspace: Optional[str]) -> int:
    """打印工作区路径与其 SID，用于确认放行目标。"""
    canonical, sid = resolve_workspace(workspace)
    sys.stdout.write(f"工作区: {canonical}\nSID   : {sid}\n")
    return 0


def cmd_grant(target: str, workspace: Optional[str]) -> int:
    """放行目录：给目标目录加一条工作区 SID 的可继承允许写入 ACE。"""
    _guard_not_sandboxed()
    canonical, sid = resolve_workspace(workspace)

    root = os.path.abspath(target)
    if not os.path.isdir(root):
        raise DshGrantError(f"目标目录不存在: {root}")

    # 目标已在工作区内时无需放行：工作区 ACE 已经覆盖它。
    # 用 normcase 对齐 Windows 的大小写不敏感语义，避免因大小写差异误判。
    ws_key = os.path.normcase(canonical).rstrip("\\/")
    tgt_key = os.path.normcase(root).rstrip("\\/")
    if tgt_key == ws_key or tgt_key.startswith(ws_key + os.sep):
        sys.stderr.write(
            f"{root} 已位于工作区 {canonical} 内，沙箱中本就可写，无需放行。\n"
        )
        return 0

    changed, failures = _grant(root, sid)
    if failures:
        for item in failures:
            sys.stderr.write(f"错误：{item}\n")
        return 1

    if changed:
        sys.stderr.write(
            f"已放行：{root}\n"
            f"  工作区 SID: {sid}（来自 {canonical}）\n"
            f"  子项通过 ACE 继承自动获得写入权限。\n"
            f"  之后所有基于该工作区的 DSH 会话都可写入此目录。\n"
        )
    else:
        sys.stderr.write(
            f"{root} 已放行（该 SID 的 ACE 已存在或从父目录继承），未做修改。\n"
        )
    return 0


def cmd_revoke(target: str, workspace: Optional[str]) -> int:
    """撤销放行：递归清除树中该 SID 的显式 ACE。"""
    _guard_not_sandboxed()
    _canonical, sid = resolve_workspace(workspace)

    root = os.path.abspath(target)
    if not os.path.isdir(root):
        raise DshGrantError(f"目标目录不存在: {root}")

    result = _revoke_tree(root, sid)
    sys.stderr.write(
        f"已扫描 {result.scanned} 个条目，撤销 {result.changed} 个：{root}\n"
    )
    if result.failures:
        sys.stderr.write(f"错误：{len(result.failures)} 个条目处理失败：\n")
        for item in result.failures:
            sys.stderr.write(f"  - {item}\n")
        return 1
    return 0


def cmd_status(target: str, workspace: Optional[str]) -> int:
    """报告目录的放行状态。只读，不修改任何 ACL。"""
    canonical, sid = resolve_workspace(workspace)

    root = os.path.abspath(target)
    if not os.path.isdir(root):
        raise DshGrantError(f"目标目录不存在: {root}")

    # 放行状态的判定要区分两种来源：
    # - 目标自身带显式 ACE：独立于父目录，撤销父目录后仍可写
    # - 仅从父目录继承：父目录撤销后即失效
    # 只报"可写"会把这两种情况混为一谈，故分开列出。
    explicit_entries: List[str] = []
    inherited_only: List[str] = []
    total = 0
    failures: List[str] = []

    sid_ptr = wws._sid_from_string(sid)
    try:
        for entry, _is_dir in wws._walk_tree(root):
            total += 1
            try:
                p_sd, p_dacl = wws._read_dacl(entry)
            except wws.SandboxError as e:
                failures.append(f"{entry}: {e}")
                continue
            try:
                explicit, inherited = wws._grant_ace_state(p_dacl, sid_ptr)
            finally:
                wws._kernel32.LocalFree(p_sd)

            if explicit:
                explicit_entries.append(entry)
            elif inherited:
                inherited_only.append(entry)
    finally:
        wws._kernel32.LocalFree(sid_ptr)

    writable = len(explicit_entries) + len(inherited_only)

    sys.stdout.write(f"目标  : {root}\n")
    sys.stdout.write(f"工作区: {canonical}\n")
    sys.stdout.write(f"SID   : {sid}\n")
    sys.stdout.write(
        f"扫描条目: {total}，其中可写入: {writable}"
        f"（显式 ACE {len(explicit_entries)}，仅继承 {len(inherited_only)}）\n"
    )

    if writable == 0:
        sys.stdout.write(
            "状态  : 未放行——DSH 沙箱中对该目录的写入会被拒绝。\n"
        )
    elif explicit_entries:
        sys.stdout.write("状态  : 已放行（目标自身带显式 ACE）。\n")
        _print_sample("显式 ACE 条目", explicit_entries)
        if inherited_only:
            _print_sample("仅继承条目", inherited_only)
    else:
        sys.stdout.write(
            "状态  : 仅通过父目录继承获得权限；父目录撤销后本目录即失效。\n"
        )
        _print_sample("仅继承条目", inherited_only)

    if failures:
        sys.stderr.write(f"错误：{len(failures)} 个条目读取失败：\n")
        for item in failures:
            sys.stderr.write(f"  - {item}\n")
        return 1
    return 0


def _print_sample(label: str, items: List[str], limit: int = 10) -> None:
    """列出条目样本，超出部分只报数量，避免大目录刷屏。"""
    shown = items[:limit]
    sys.stdout.write(f"  {label}（共 {len(items)}）:\n")
    for item in shown:
        sys.stdout.write(f"    {item}\n")
    if len(items) > limit:
        sys.stdout.write(f"    ...另有 {len(items) - limit} 项\n")


# ── 入口 ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dsh_sandbox_grant.py",
        description=(
            "管理 DSH 写入沙箱的目录放行。放行需在沙箱外的普通终端执行。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  dsh_sandbox_grant.py grant C:\\data\\out\n"
            "  dsh_sandbox_grant.py status C:\\data\\out\n"
            "  dsh_sandbox_grant.py revoke C:\\data\\out\n"
            "  dsh_sandbox_grant.py sid --workspace C:\\Workspaces\\scripts\n"
        ),
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="DSH 工作区路径（默认: 当前工作目录）。放行 SID 由它派生。",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    for name, help_text in (
        ("grant", "放行目录：加可继承写入 ACE"),
        ("revoke", "撤销放行：递归清除显式 ACE"),
        ("status", "查看放行状态（只读）"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("target", help="目标目录")
        p.add_argument(
            "--workspace",
            default=None,
            help="DSH 工作区路径（默认: 当前工作目录）。放行 SID 由它派生。",
        )

    sid_parser = sub.add_parser("sid", help="打印工作区路径与其 SID")
    sid_parser.add_argument(
        "--workspace",
        default=None,
        help="DSH 工作区路径（默认: 当前工作目录）",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        sys.stderr.write("错误：DSH 写入沙箱仅在 Windows 上可用。\n")
        return 1

    # argparse 的子解析器会用自己的默认值覆盖主解析器已解析的 --workspace，
    # 因此 `--workspace X grant <dir>` 会被子命令的 None 覆盖。
    # 子解析器同样接受该参数，这里显式回退到主解析器位置上的取值。
    if args.workspace is None:
        args.workspace = _workspace_before_action(
            sys.argv[1:] if argv is None else argv
        )

    try:
        if args.action == "sid":
            return cmd_sid(args.workspace)
        if args.action == "grant":
            return cmd_grant(args.target, args.workspace)
        if args.action == "revoke":
            return cmd_revoke(args.target, args.workspace)
        if args.action == "status":
            return cmd_status(args.target, args.workspace)
    except DshGrantError as e:
        sys.stderr.write(f"错误：{e}\n")
        return 1
    except wws.SandboxError as e:
        sys.stderr.write(f"错误：{e}\n")
        return 1

    sys.stderr.write(f"错误：未知操作 {args.action}\n")
    return 1


# 子命令名，用于定位 argv 中动作出现的位置
_ACTIONS = ("grant", "revoke", "status", "sid")


def _workspace_before_action(argv: List[str]) -> Optional[str]:
    """提取子命令之前的 --workspace 取值。

    子解析器会用默认值覆盖主解析器的结果，因此这里直接扫原始 argv，
    只认子命令之前出现的那一个 --workspace。
    """
    for index, token in enumerate(argv):
        if token in _ACTIONS:
            return None
        if token == "--workspace" and index + 1 < len(argv):
            return argv[index + 1]
        if token.startswith("--workspace="):
            return token.split("=", 1)[1]
    return None


if __name__ == "__main__":
    sys.exit(main())
