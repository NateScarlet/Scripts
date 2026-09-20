
"""Windows 写入沙箱：将 pwsh 子进程的写入限制在当前工作目录内。

机制来自 @deepseek-ai/dsh-sandbox-windows-acl（huoyaoyuan/windows-acl-restrict-poc 的移植）：

- 从规范工作区路径确定性派生工作区能力 SID（sha256 → S-1-4-x-y）
- 给工作目录 ACL 添加该 SID 的允许写入 ACE（常驻，不清理，exact-ACE skip）
- 创建 WRITE_RESTRICTED 受限令牌，restricting SIDs = [工作区 SID, Everyone, Logon SID]
- 用受限令牌通过 CreateProcessAsUserW 启动 pwsh.exe

任何 Win32 调用失败都抛出 SandboxError，绝不降级为不受限执行（fail closed）。

限制范围：只防写，不防读。写入被 ACL 拒绝时命令以非零退出码失败。
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import hashlib
import msvcrt
import os
import struct
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

if sys.platform != "win32":
    raise ImportError("win_write_sandbox 仅在 Windows 上可用")


# ── CreateRestrictedToken 标志 ─────────────────────────────────────

_DISABLE_MAX_PRIVILEGE = 0x01
_LUA_TOKEN = 0x04
_WRITE_RESTRICTED = 0x08

# 与 dsh 一致：WRITE_RESTRICTED | DISABLE_MAX_PRIVILEGE | LUA_TOKEN
_RESTRICTED_TOKEN_FLAGS = _DISABLE_MAX_PRIVILEGE | _LUA_TOKEN | _WRITE_RESTRICTED


# ── 访问掩码 ──────────────────────────────────────────────────────

_FILE_GENERIC_WRITE = 0x00120116
_DELETE = 0x00010000
_FILE_DELETE_CHILD = 0x00000040

# 覆盖工作目录内的所有写操作：写数据、追加、写 EA、写属性、删除文件、删除子项。
# 刻意不含 WRITE_DAC / WRITE_OWNER：受限进程若能改写 ACL 就能逃逸沙箱。
_GRANT_MASK = _FILE_GENERIC_WRITE | _DELETE | _FILE_DELETE_CHILD


# ── ACE / ACL 常量 ────────────────────────────────────────────────

_CONTAINER_INHERIT_ACE = 0x2
_OBJECT_INHERIT_ACE = 0x1
_ACE_INHERIT_FLAGS = _CONTAINER_INHERIT_ACE | _OBJECT_INHERIT_ACE

_GRANT_ACCESS = 1
_TRUSTEE_IS_SID = 0
_TRUSTEE_IS_UNKNOWN = 0

_SE_FILE_OBJECT = 1
_DACL_SECURITY_INFORMATION = 0x00000004
_ERROR_SUCCESS = 0


# ── 令牌信息类 ────────────────────────────────────────────────────

_TokenUser = 1
_TokenGroups = 2
_SE_GROUP_LOGON_ID = 0xC0000000


# ── 进程创建 ──────────────────────────────────────────────────────

_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_STARTF_USESTDHANDLES = 0x00000100
_STARTF_USESHOWWINDOW = 0x00000001
_SW_HIDE = 0
_HANDLE_FLAG_INHERIT = 0x00000001
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_TOKEN_DUPLICATE = 0x0002
_TOKEN_QUERY = 0x0008
_TOKEN_ADJUST_DEFAULT = 0x0080
_TOKEN_ASSIGN_PRIMARY = 0x0001

# TOKEN_INFORMATION_CLASS 取值
_TokenDefaultDacl = 6

_FILE_ALL_ACCESS = 0x001F01FF

_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3

_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


# ── ctypes 结构体 ─────────────────────────────────────────────────


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", ctypes.c_void_p),
        ("Attributes", wintypes.DWORD),
    ]


class TOKEN_GROUPS(ctypes.Structure):
    _fields_ = [
        ("GroupCount", wintypes.DWORD),
        ("Groups", SID_AND_ATTRIBUTES * 1),  # 变长，实际通过指针运算访问
    ]


class TRUSTEE_W(ctypes.Structure):
    _fields_ = [
        ("pMultipleTrustee", ctypes.c_void_p),
        ("MultipleTrusteeOperation", wintypes.DWORD),
        ("TrusteeForm", wintypes.DWORD),
        ("TrusteeType", wintypes.DWORD),
        ("ptstrName", ctypes.c_void_p),
    ]


class EXPLICIT_ACCESS_W(ctypes.Structure):
    _fields_ = [
        ("grfAccessPermissions", wintypes.DWORD),
        ("grfAccessMode", wintypes.DWORD),
        ("grfInheritance", wintypes.DWORD),
        ("Trustee", TRUSTEE_W),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]



# ── DLL 加载与函数签名 ────────────────────────────────────────────

_advapi32 = ctypes.WinDLL("advapi32.dll", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)

_advapi32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
_advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL

_advapi32.GetLengthSid.argtypes = [ctypes.c_void_p]
_advapi32.GetLengthSid.restype = wintypes.DWORD

_advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
]
_advapi32.OpenProcessToken.restype = wintypes.BOOL

_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE

_advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_advapi32.EqualSid.restype = wintypes.BOOL

_advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
]
_advapi32.GetTokenInformation.restype = wintypes.BOOL

_advapi32.CreateRestrictedToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD,
    wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, ctypes.c_void_p,
    ctypes.POINTER(wintypes.HANDLE),
]
_advapi32.CreateRestrictedToken.restype = wintypes.BOOL

_advapi32.GetNamedSecurityInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
_advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD

_advapi32.SetEntriesInAclW.argtypes = [
    wintypes.ULONG, ctypes.POINTER(EXPLICIT_ACCESS_W),
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
]
_advapi32.SetEntriesInAclW.restype = wintypes.DWORD

_advapi32.SetNamedSecurityInfoW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
_advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD

_advapi32.GetExplicitEntriesFromAclW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG),
    ctypes.POINTER(ctypes.POINTER(EXPLICIT_ACCESS_W)),
]
_advapi32.GetExplicitEntriesFromAclW.restype = wintypes.DWORD

_advapi32.CreateProcessAsUserW.argtypes = [
    wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
    wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p,
]
_advapi32.CreateProcessAsUserW.restype = wintypes.BOOL

_advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
]
_advapi32.OpenProcessToken.restype = wintypes.BOOL

_advapi32.SetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
]
_advapi32.SetTokenInformation.restype = wintypes.BOOL

_kernel32.GetCurrentProcess.argtypes = []
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE

_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p

_kernel32.CreatePipe.argtypes = [
    ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE),
    ctypes.c_void_p, wintypes.DWORD,
]
_kernel32.CreatePipe.restype = wintypes.BOOL

_kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
_kernel32.SetHandleInformation.restype = wintypes.BOOL

_kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetExitCodeProcess.restype = wintypes.BOOL

_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD

_kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
_kernel32.TerminateProcess.restype = wintypes.BOOL

_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE


# ── 异常 ──────────────────────────────────────────────────────────


class SandboxError(Exception):
    """沙箱创建或进程启动失败。"""


# ── SID 工具 ──────────────────────────────────────────────────────


def workspace_write_sid(workspace_root: str) -> str:
    """从规范工作区路径确定性派生工作区能力 SID。

    算法与 dsh 的 workspaceWriteSid 一致：
    sha256(规范路径) 前 8 字节 → 两个 30 位子权威 → S-1-4-x-y。
    同一路径永远产生同一 SID，不同路径产生不同 SID。
    """
    canonical = os.path.realpath(workspace_root)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    first = (struct.unpack_from("<I", digest, 0)[0] % (2**30 - 1)) + 1
    second = (struct.unpack_from("<I", digest, 4)[0] % (2**30 - 1)) + 1
    return f"S-1-4-{first}-{second}"


def _sid_from_string(sid_str: str) -> ctypes.c_void_p:
    """字符串 SID → 二进制 SID 指针。调用方负责 LocalFree。"""
    sid = ctypes.c_void_p()
    if not _advapi32.ConvertStringSidToSidW(sid_str, ctypes.byref(sid)):
        raise SandboxError(
            f"ConvertStringSidToSidW({sid_str!r}) 失败: {ctypes.get_last_error()}"
        )
    return sid


def _sid_equal(sid1: ctypes.c_void_p, sid2: ctypes.c_void_p) -> bool:
    return bool(_advapi32.EqualSid(sid1, sid2))


def _get_logon_sid(
    token: wintypes.HANDLE,
) -> Tuple[ctypes.c_void_p, Any]:
    """从进程令牌的 TokenGroups 中提取 Logon SID（SE_GROUP_LOGON_ID）。

    Logon SID 必须保留在 restricting SIDs 中，否则进程初始化会失败。
    """
    size = wintypes.DWORD(0)
    _advapi32.GetTokenInformation(token, _TokenGroups, None, 0, ctypes.byref(size))
    if size.value == 0:
        raise SandboxError(
            f"GetTokenInformation(TokenGroups, 大小探测) 失败: {ctypes.get_last_error()}"
        )

    buf = ctypes.create_string_buffer(size.value)
    if not _advapi32.GetTokenInformation(
        token, _TokenGroups, buf, size.value, ctypes.byref(size)
    ):
        raise SandboxError(
            f"GetTokenInformation(TokenGroups) 失败: {ctypes.get_last_error()}"
        )

    groups_ptr = ctypes.cast(buf, ctypes.POINTER(TOKEN_GROUPS))
    count = groups_ptr.contents.GroupCount

    # TOKEN_GROUPS 是变长结构，Groups 数组从结构体偏移处开始。
    # 通过基址 + 数组元素大小逐项访问，避免声明固定长度数组。
    base = ctypes.addressof(groups_ptr.contents)
    groups_offset = TOKEN_GROUPS.Groups.offset
    elem_size = ctypes.sizeof(SID_AND_ATTRIBUTES)

    for i in range(count):
        item_addr = base + groups_offset + i * elem_size
        item = ctypes.cast(item_addr, ctypes.POINTER(SID_AND_ATTRIBUTES)).contents
        if item.Attributes & _SE_GROUP_LOGON_ID:
            # 复制 SID 到独立缓冲区。TOKEN_GROUPS 缓冲区在函数返回后释放，
            # 且调用方需要缓冲区存活到令牌创建完成，因此连同缓冲区一起返回，
            # 由调用方持有引用，避免指针悬空。
            sid_len = _advapi32.GetLengthSid(item.Sid)
            sid_copy = ctypes.create_string_buffer(sid_len)
            ctypes.memmove(sid_copy, item.Sid, sid_len)
            return ctypes.cast(sid_copy, ctypes.c_void_p), sid_copy

    raise SandboxError("进程令牌中未找到 Logon SID（SE_GROUP_LOGON_ID）")


# ── ACL 工具 ──────────────────────────────────────────────────────


def _grant_ace_exists(p_dacl: ctypes.c_void_p, sid_ptr: ctypes.c_void_p) -> bool:
    """检查 DACL 中是否已有匹配的允许写入 ACE（exact-ACE skip）。"""
    if not p_dacl:
        return False

    count = wintypes.ULONG(0)
    entries = ctypes.POINTER(EXPLICIT_ACCESS_W)()
    result = _advapi32.GetExplicitEntriesFromAclW(
        p_dacl, ctypes.byref(count), ctypes.byref(entries)
    )
    if result != _ERROR_SUCCESS:
        return False

    try:
        for i in range(count.value):
            ea = entries[i]
            if (
                ea.grfAccessPermissions == _GRANT_MASK
                and ea.grfAccessMode == _GRANT_ACCESS
                and ea.grfInheritance == _ACE_INHERIT_FLAGS
                and ea.Trustee.TrusteeForm == _TRUSTEE_IS_SID
                and ea.Trustee.ptstrName
                and _sid_equal(ea.Trustee.ptstrName, sid_ptr)
            ):
                return True
        return False
    finally:
        _kernel32.LocalFree(ctypes.cast(entries, ctypes.c_void_p))


def _ensure_workspace_ace(directory: str, sid_ptr: ctypes.c_void_p) -> None:
    """确保工作目录的 DACL 中存在能力 SID 的允许写入 ACE。

    ACE 常驻不清理（dsh 逻辑）。已存在时跳过（exact-ACE skip）。
    """
    p_sd = ctypes.c_void_p()
    p_dacl = ctypes.c_void_p()
    result = _advapi32.GetNamedSecurityInfoW(
        directory, _SE_FILE_OBJECT, _DACL_SECURITY_INFORMATION,
        None, None, ctypes.byref(p_dacl), None, ctypes.byref(p_sd),
    )
    if result != _ERROR_SUCCESS:
        raise SandboxError(
            f"GetNamedSecurityInfoW({directory!r}) 失败: {result}"
        )

    try:
        if _grant_ace_exists(p_dacl, sid_ptr):
            return

        ea = EXPLICIT_ACCESS_W()
        ea.grfAccessPermissions = _GRANT_MASK
        ea.grfAccessMode = _GRANT_ACCESS
        ea.grfInheritance = _ACE_INHERIT_FLAGS
        ea.Trustee.TrusteeForm = _TRUSTEE_IS_SID
        ea.Trustee.TrusteeType = _TRUSTEE_IS_UNKNOWN
        ea.Trustee.ptstrName = ctypes.cast(sid_ptr, ctypes.c_void_p)

        new_acl = ctypes.c_void_p()
        result = _advapi32.SetEntriesInAclW(
            1, ctypes.byref(ea), p_dacl, ctypes.byref(new_acl)
        )
        if result != _ERROR_SUCCESS:
            raise SandboxError(f"SetEntriesInAclW 失败: {result}")

        try:
            result = _advapi32.SetNamedSecurityInfoW(
                directory, _SE_FILE_OBJECT, _DACL_SECURITY_INFORMATION,
                None, None, new_acl, None,
            )
            if result != _ERROR_SUCCESS:
                raise SandboxError(
                    f"SetNamedSecurityInfoW({directory!r}) 失败: {result}"
                )
        finally:
            _kernel32.LocalFree(new_acl)
    finally:
        _kernel32.LocalFree(p_sd)


# ── 令牌工具 ──────────────────────────────────────────────────────

# TOKEN_INFORMATION_CLASS 取值：令牌的 restricting SID 列表
_TokenRestrictedSids = 11


def _restricting_sid_count() -> int:
    """返回当前进程令牌的 restricting SID 数量；0 表示令牌不受限。

    已受限的进程（例如 chat2cli 运行在自身沙箱内）不能再基于该令牌调用
    CreateRestrictedToken：那会因令牌已是受限令牌而以 ERROR_INVALID_PARAMETER
    失败。此时子进程通过普通进程创建即可继承写限制。
    """
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(
        _kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
    ):
        raise SandboxError(f"OpenProcessToken 失败: {ctypes.get_last_error()}")
    try:
        size = wintypes.DWORD(0)
        # 不受限的令牌没有该信息，查询返回 0 字节，属于预期情况
        _advapi32.GetTokenInformation(
            token, _TokenRestrictedSids, None, 0, ctypes.byref(size)
        )
        if size.value == 0:
            return 0
        buf = ctypes.create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(
            token, _TokenRestrictedSids, buf, size.value, ctypes.byref(size)
        ):
            raise SandboxError(
                "GetTokenInformation(TokenRestrictedSids) 失败: "
                f"{ctypes.get_last_error()}"
            )
        return ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
    finally:
        _kernel32.CloseHandle(token)


def _set_token_default_dacl_grant(
    token: wintypes.HANDLE, sid_ptr: ctypes.c_void_p
) -> None:
    """向受限令牌的默认 DACL 合并一条 restricting SID 的完全访问 ACE。

    受限令牌逐字继承用户的默认 DACL，其中不含任何 restricting SID。
    子进程创建新对象（如标准流管道）时，WRITE_RESTRICTED 的 pass-2
    检查要求对象 DACL 中存在 restricting SID 的允许 ACE，否则创建失败
    （ERROR_ACCESS_DENIED，表现为 CreateProcessAsUserW 返回 5）。

    合并的 ACE 命名的是一个 restricting SID，因此新建对象自身的 DACL
    可以通过 pass-2 检查，而对象创建本身仍受父容器 DACL 约束：
    白名单目录之外的文件依然无法创建。
    """
    needed = wintypes.DWORD(0)
    _advapi32.GetTokenInformation(
        token, _TokenDefaultDacl, None, 0, ctypes.byref(needed)
    )
    if needed.value == 0:
        raise SandboxError(
            "GetTokenInformation(TokenDefaultDacl, 大小探测) 失败: "
            f"{ctypes.get_last_error()}"
        )

    buf = ctypes.create_string_buffer(needed.value)
    if not _advapi32.GetTokenInformation(
        token, _TokenDefaultDacl, buf, needed.value, ctypes.byref(needed)
    ):
        raise SandboxError(
            "GetTokenInformation(TokenDefaultDacl) 失败: "
            f"{ctypes.get_last_error()}"
        )

    # TOKEN_DEFAULT_DACL 结构体只有一个 PACL 字段，直接读首指针
    current_dacl = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
    if not current_dacl:
        raise SandboxError("令牌没有默认 DACL 可供扩展")

    ea = EXPLICIT_ACCESS_W()
    ea.grfAccessPermissions = _FILE_ALL_ACCESS
    ea.grfAccessMode = _GRANT_ACCESS
    ea.grfInheritance = 0
    ea.Trustee.TrusteeForm = _TRUSTEE_IS_SID
    ea.Trustee.TrusteeType = _TRUSTEE_IS_UNKNOWN
    ea.Trustee.ptstrName = ctypes.cast(sid_ptr, ctypes.c_void_p)

    new_dacl = ctypes.c_void_p()
    result = _advapi32.SetEntriesInAclW(
        1, ctypes.byref(ea), current_dacl, ctypes.byref(new_dacl)
    )
    if result != _ERROR_SUCCESS:
        raise SandboxError(f"SetEntriesInAclW(默认 DACL 合并) 失败: {result}")

    try:
        # SetTokenInformation 在返回前复制 ACL，之后即可释放 new_dacl
        info = ctypes.c_void_p(new_dacl.value)
        if not _advapi32.SetTokenInformation(
            token, _TokenDefaultDacl, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise SandboxError(
                "SetTokenInformation(TokenDefaultDacl) 失败: "
                f"{ctypes.get_last_error()}"
            )
    finally:
        _kernel32.LocalFree(new_dacl)


def _create_restricted_token(
    token: wintypes.HANDLE,
    restricting_sids: List[ctypes.c_void_p],
) -> wintypes.HANDLE:
    """创建 WRITE_RESTRICTED 受限令牌。"""
    sid_array = (SID_AND_ATTRIBUTES * len(restricting_sids))()
    for i, sid_ptr in enumerate(restricting_sids):
        sid_array[i].Sid = sid_ptr
        sid_array[i].Attributes = 0

    new_token = wintypes.HANDLE()
    if not _advapi32.CreateRestrictedToken(
        token,
        _RESTRICTED_TOKEN_FLAGS,
        0, None,
        0, None,
        len(restricting_sids), sid_array,
        ctypes.byref(new_token),
    ):
        raise SandboxError(
            f"CreateRestrictedToken 失败: {ctypes.get_last_error()}"
        )
    return new_token


# ── 环境块 ────────────────────────────────────────────────────────


def _build_environment_block(env: Dict[str, str]) -> ctypes.c_void_p:
    """构建 Windows 进程环境块（双 null 结尾的 Unicode 字符串）。

    不继承父进程环境，只使用传入的 env。
    """
    entries: List[str] = []
    for key in sorted(env.keys()):
        entries.append(f"{key}={env[key]}")
    block = "\0".join(entries) + "\0\0"
    # 返回缓冲区对象本身而非裸指针：CreateProcessAsUserW 要求可写内存，
    # 且调用方必须持有缓冲区引用，否则内容被回收后指针悬空。
    return ctypes.create_unicode_buffer(block)


# ── 进程包装 ──────────────────────────────────────────────────────


class SandboxedProcess:
    """封装沙箱子进程，提供与 subprocess.Popen 兼容的接口。

    暴露 stdout / stderr（Python 文件对象）、pid、wait()、terminate()、kill()。

    有两种后端：
    - 受限令牌后端：持有原生进程句柄，用 Win32 API 等待与终止。
    - 继承后端：当前进程已受限时，用 subprocess.Popen 创建子进程，
      子进程继承 restricting SIDs，复用 Popen 的等待与终止。
    """

    def __init__(
        self,
        h_process: Optional[wintypes.HANDLE],
        pid: int,
        stdout_file: Any,
        stderr_file: Any,
        popen: Optional[Any] = None,
    ):
        self._h_process = h_process
        self._popen = popen
        self.pid = pid
        self.stdout = stdout_file
        self.stderr = stderr_file
        self.returncode: Optional[int] = None

    @classmethod
    def from_popen(cls, popen: Any) -> "SandboxedProcess":
        """包装 subprocess.Popen，对外接口与受限令牌后端一致。"""
        return cls(None, popen.pid, popen.stdout, popen.stderr, popen=popen)

    def wait(self, timeout: Optional[float] = None) -> int:
        """等待进程结束，返回退出码。timeout 为 None 时无限等待。"""
        if self.returncode is not None:
            return self.returncode

        if self._popen is not None:
            self.returncode = self._popen.wait(timeout=timeout)
            return self.returncode

        if timeout is None:
            ms = 0xFFFFFFFF  # INFINITE
        else:
            ms = int(timeout * 1000)

        result = _kernel32.WaitForSingleObject(self._h_process, ms)
        if result == _WAIT_TIMEOUT:
            # 与 subprocess 语义保持一致，调用方依赖此异常类型做超时清理
            raise subprocess.TimeoutExpired("pwsh.exe", timeout)
        if result != _WAIT_OBJECT_0:
            raise SandboxError(f"WaitForSingleObject 失败: {ctypes.get_last_error()}")

        code = wintypes.DWORD()
        if not _kernel32.GetExitCodeProcess(self._h_process, ctypes.byref(code)):
            raise SandboxError(f"GetExitCodeProcess 失败: {ctypes.get_last_error()}")
        self.returncode = code.value
        return self.returncode

    def terminate(self) -> None:
        if self._popen is not None:
            self._popen.terminate()
            return
        if self.returncode is None:
            _kernel32.TerminateProcess(self._h_process, 1)

    def kill(self) -> None:
        if self._popen is not None:
            self._popen.kill()
            return
        self.terminate()

    def close_handles(self) -> None:
        """关闭原生进程句柄与管道文件对象。"""
        if self._h_process:
            _kernel32.CloseHandle(self._h_process)
            self._h_process = None
        for f in (self.stdout, self.stderr):
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass


# ── 对外接口 ──────────────────────────────────────────────────────


def _spawn_inheriting_restrictions(
    command: str, cwd: str, env: Dict[str, str]
) -> SandboxedProcess:
    """当前进程已受限时，用普通进程创建让子进程继承写限制。

    子进程继承 restricting SIDs，写入边界与父进程一致；同时避免在受限令牌
    上再次调用 CreateRestrictedToken（会以 ERROR_INVALID_PARAMETER 失败），
    并让 pwsh 保持 FullLanguage。
    """
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    popen = subprocess.Popen(
        ["pwsh.exe", "-NoProfile", "-EncodedCommand", encoded],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        stdin=subprocess.DEVNULL,
    )
    return SandboxedProcess.from_popen(popen)


def spawn_pwsh_sandboxed(
    command: str,
    cwd: str,
    env: Dict[str, str],
) -> SandboxedProcess:
    """在 Windows 写入沙箱中启动 pwsh.exe。

    写入限制在 cwd 内。任何 Win32 失败都抛出 SandboxError，
    绝不降级为不受限执行。

    参数：
        command: 完整的 PowerShell 命令字符串（已包含包装前缀）
        cwd: 工作目录（沙箱的可写根）
        env: 子进程环境变量

    返回 SandboxedProcess，调用方负责在结束时调用 close_handles()。
    """
    cwd_abs = os.path.abspath(cwd)
    if not os.path.isdir(cwd_abs):
        raise SandboxError(f"工作目录不存在: {cwd_abs}")

    # 当前进程已受限（例如 chat2cli 运行在自身沙箱内）时，子进程通过普通
    # 进程创建即可继承写限制，不需要也无法再创建受限令牌。
    if _restricting_sid_count() > 0:
        return _spawn_inheriting_restrictions(command, cwd_abs, env)

    # 1. 派生工作区能力 SID
    sid_str = workspace_write_sid(cwd_abs)
    ws_sid = _sid_from_string(sid_str)

    # 2. 获取 Everyone SID
    everyone_sid = _sid_from_string("S-1-1-0")

    # 3. 获取当前进程令牌和 Logon SID
    current_token = wintypes.HANDLE()
    # TOKEN_DUPLICATE 供 CreateRestrictedToken 复制令牌，
    # TOKEN_QUERY 供读取 TokenGroups，
    # TOKEN_ADJUST_DEFAULT 供修改受限令牌的默认 DACL，
    # TOKEN_ASSIGN_PRIMARY 供 CreateProcessAsUserW 启动进程：
    # 缺少它时调用者必须持有 SeAssignPrimaryTokenPrivilege（普通用户没有），
    # 否则返回 ERROR_ACCESS_DENIED (5)。
    if not _advapi32.OpenProcessToken(
        _kernel32.GetCurrentProcess(),
        _TOKEN_DUPLICATE
        | _TOKEN_QUERY
        | _TOKEN_ADJUST_DEFAULT
        | _TOKEN_ASSIGN_PRIMARY,
        ctypes.byref(current_token),
    ):
        raise SandboxError(
            f"OpenProcessToken 失败: {ctypes.get_last_error()}"
        )

    logon_buf: Any = None
    try:
        # logon_buf 必须在令牌创建完成前保持存活，因此作为局部变量持有
        logon_sid, logon_buf = _get_logon_sid(current_token)

        # 4. 确保工作目录 ACE 存在
        _ensure_workspace_ace(cwd_abs, ws_sid)

        # 5. 创建受限令牌
        restricted_token = _create_restricted_token(
            current_token,
            [ws_sid, everyone_sid, logon_sid],
        )

        # 5b. 把工作区 SID 的允许 ACE 合并进受限令牌的默认 DACL。
        # 缺少这一步时，子进程创建标准流管道会被 pass-2 写入检查拒绝，
        # 表现为 CreateProcessAsUserW 返回 ERROR_ACCESS_DENIED (5)。
        _set_token_default_dacl_grant(restricted_token, ws_sid)

        try:
            # 6. 创建管道
            stdout_read = wintypes.HANDLE()
            stdout_write = wintypes.HANDLE()
            stderr_read = wintypes.HANDLE()
            stderr_write = wintypes.HANDLE()

            if not _kernel32.CreatePipe(
                ctypes.byref(stdout_read), ctypes.byref(stdout_write),
                None, 0,
            ):
                raise SandboxError(
                    f"CreatePipe(stdout) 失败: {ctypes.get_last_error()}"
                )
            if not _kernel32.CreatePipe(
                ctypes.byref(stderr_read), ctypes.byref(stderr_write),
                None, 0,
            ):
                _kernel32.CloseHandle(stdout_read)
                _kernel32.CloseHandle(stdout_write)
                raise SandboxError(
                    f"CreatePipe(stderr) 失败: {ctypes.get_last_error()}"
                )

            # 只有写端可被子进程继承；读端显式禁止继承，
            # 否则子进程持有读端会导致父进程侧管道收不到 EOF。
            for h in (stdout_write, stderr_write):
                if not _kernel32.SetHandleInformation(
                    h, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
                ):
                    raise SandboxError(
                        f"SetHandleInformation 失败: {ctypes.get_last_error()}"
                    )
            for h in (stdout_read, stderr_read):
                if not _kernel32.SetHandleInformation(h, _HANDLE_FLAG_INHERIT, 0):
                    raise SandboxError(
                        f"SetHandleInformation 失败: {ctypes.get_last_error()}"
                    )

            try:
                # 7. 构建 STARTUPINFO。STARTF_USESTDHANDLES 要求三个句柄都有效，
                # 否则子进程的标准输入可能继承到父进程不可用的句柄。
                # STARTF_USESTDHANDLES 要求三个句柄在子进程中可用，
                # NUL 句柄必须是可继承的，否则子进程打开标准输入时被拒绝。
                nul_handle = _kernel32.CreateFileW(
                    "NUL", _GENERIC_READ,
                    _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                    None, _OPEN_EXISTING, 0, None,
                )
                # CreateFileW 的 restype 是 HANDLE，ctypes 返回 Python int
                if not nul_handle or nul_handle == _INVALID_HANDLE_VALUE:
                    raise SandboxError(
                        f"打开 NUL 设备失败: {ctypes.get_last_error()}"
                    )
                if not _kernel32.SetHandleInformation(
                    nul_handle, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
                ):
                    _kernel32.CloseHandle(nul_handle)
                    raise SandboxError(
                        f"SetHandleInformation(NUL) 失败: {ctypes.get_last_error()}"
                    )

                # lpDesktop 保持 NULL，让子进程继承父进程的桌面。
                # 显式指定 winsta0\default 需要同时调整该桌面 DACL 授予
                # 登录会话访问权限，否则 CreateProcessAsUserW 返回
                # ERROR_ACCESS_DENIED (5)。dsh 同样传 NULL。
                si = STARTUPINFOW()
                si.cb = ctypes.sizeof(si)
                si.dwFlags = _STARTF_USESTDHANDLES | _STARTF_USESHOWWINDOW
                si.wShowWindow = _SW_HIDE
                si.hStdInput = nul_handle
                si.hStdOutput = stdout_write
                si.hStdError = stderr_write

                pi = PROCESS_INFORMATION()

                env_block = _build_environment_block(env)

                # 命令行用 -EncodedCommand 传递（UTF-16LE + base64），
                # 避免命令中的引号、换行或特殊字符破坏命令行解析。
                encoded = base64.b64encode(
                    command.encode("utf-16-le")
                ).decode("ascii")
                cmdline = ctypes.create_unicode_buffer(
                    f"pwsh.exe -NoProfile -EncodedCommand {encoded}"
                )

                # 8. 启动进程
                if not _advapi32.CreateProcessAsUserW(
                    restricted_token,
                    None,
                    cmdline,
                    None, None, True,
                    _CREATE_UNICODE_ENVIRONMENT,
                    ctypes.cast(env_block, ctypes.c_void_p),
                    cwd_abs,
                    ctypes.byref(si),
                    ctypes.byref(pi),
                ):
                    _kernel32.CloseHandle(nul_handle)
                    raise SandboxError(
                        f"CreateProcessAsUserW 失败: {ctypes.get_last_error()}"
                    )

                # 主线程句柄与 NUL 设备不再需要，立即关闭避免泄漏
                _kernel32.CloseHandle(pi.hThread)
                _kernel32.CloseHandle(nul_handle)

                # 父进程关闭写端，子进程已持有自己的副本；
                # 置 None 防止 finally 重复关闭同一句柄。
                _kernel32.CloseHandle(stdout_write)
                _kernel32.CloseHandle(stderr_write)
                stdout_write = None
                stderr_write = None

                # 将读端句柄包装为 Python 文件对象。
                # open_osfhandle 接管句柄所有权，置 None 防止 finally 重复关闭。
                stdout_fd = msvcrt.open_osfhandle(
                    stdout_read.value, os.O_RDONLY
                )
                stderr_fd = msvcrt.open_osfhandle(
                    stderr_read.value, os.O_RDONLY
                )
                stdout_read = None
                stderr_read = None
                stdout_file = os.fdopen(
                    stdout_fd, "r", encoding="utf-8", errors="replace"
                )
                stderr_file = os.fdopen(
                    stderr_fd, "r", encoding="utf-8", errors="replace"
                )

                return SandboxedProcess(
                    pi.hProcess, pi.dwProcessId, stdout_file, stderr_file
                )
            finally:
                # 清理尚未移交的句柄；成功路径上相关变量已置 None
                for h in (stdout_read, stderr_read, stdout_write, stderr_write):
                    if h is not None and h.value:
                        _kernel32.CloseHandle(h)
        finally:
            _kernel32.CloseHandle(restricted_token)
    finally:
        _kernel32.CloseHandle(current_token)
        _kernel32.LocalFree(ws_sid)
        _kernel32.LocalFree(everyone_sid)
        # logon_sid 指向 logon_buf（Python 缓冲区），由 Python 回收，
        # 不能用 LocalFree 释放。
        del logon_buf


# ── Python 运行时适配 ─────────────────────────────────────────────

# CPython 的 os_mkdir_impl 在 Windows 上对 mode == 0o700 单独使用一条硬编码的
# 受保护安全描述符 D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)，
# 带 P 标志表示不继承父目录 ACE，因此新建目录上没有工作区能力 SID。
# 写入沙箱的 restricting SID 里不含 owner SID，目录随即对所有沙箱进程
# 不可访问，tempfile.mkdtemp / TemporaryDirectory 等一律失败。
#
# 该钩子把 0o700 改写为 0o755：后者走 CreateDirectoryW(path, NULL)，
# 正常继承父目录 ACE。Windows 上两者差异仅在 DACL 是否继承，
# 对同一用户下的进程没有实际保护差异。
_PY_SITECUSTOMIZE = '''\
"""由 win_write_sandbox 注入，修正 Windows 写入沙箱内的目录创建。"""

import os as _os

_original_mkdir = _os.mkdir


def _mkdir(path, mode=0o777, *args, **kwargs):
    # 0o700 会让 CPython 传入受保护安全描述符，阻断沙箱 ACE 继承。
    if mode == 0o700:
        mode = 0o755
    return _original_mkdir(path, mode, *args, **kwargs)


_os.mkdir = _mkdir
'''


def ensure_python_sitecustomize(hook_dir: str) -> str:
    """确保沙箱 Python 启动钩子存在，返回应加入 PYTHONPATH 的目录。

    写入是幂等的：内容一致时不重写，避免每次执行都触碰文件。
    """
    os.makedirs(hook_dir, exist_ok=True)
    hook_path = os.path.join(hook_dir, "sitecustomize.py")
    existing = ""
    if os.path.isfile(hook_path):
        with open(hook_path, "r", encoding="utf-8", newline="") as f:
            existing = f.read()
    if existing != _PY_SITECUSTOMIZE:
        with open(hook_path, "w", encoding="utf-8", newline="") as f:
            f.write(_PY_SITECUSTOMIZE)
    return hook_dir


# ── 写入拒绝检测 ──────────────────────────────────────────────────

_WRITE_DENIAL_PATTERNS = (
    "Access is denied",
    "Access to the path",
    "UnauthorizedAccessException",
    "拒绝访问",
    "权限不足",
    "Permission denied",
)


def current_process_is_sandboxed() -> bool:
    """当前进程是否已运行在写入沙箱内（令牌带 restricting SID）。

    决定子进程的沙箱来源：已受限时子进程继承同一 restricting 集合，
    可写范围与父进程一致；未受限时子进程获得全新的工作区沙箱。
    """
    return _restricting_sid_count() > 0


def detect_write_denial(stderr: str) -> Optional[str]:
    """检测 stderr 中是否包含写入被拒绝的迹象，返回提示文本或 None。"""
    for pattern in _WRITE_DENIAL_PATTERNS:
        if pattern in stderr:
            return (
                "检测到写入被沙箱拒绝。当前 pwsh 只能写入工作目录 "
                f"({os.getcwd()})。如需写入其他目录，请在对应目录下重新运行 "
                "chat2cli，或使用 --danger-full-access 关闭沙箱。"
            )
    return None

