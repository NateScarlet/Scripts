
"""Windows 写入沙箱：将 pwsh 子进程的写入限制在当前工作目录内。

机制对照 @deepseek-ai/dsh-sandbox-windows-acl 0.1.7：

- 从规范工作区路径确定性派生工作区能力 SID（sha256 → S-1-4-x-y）
- 给工作目录写入三件套授权，缺一不可：
  1. 该 SID 的允许写入 ACE，掩码精确为 GRANT_MASK(0x110156)，可继承
  2. 对 Everyone 的 FILE_DELETE_CHILD 拒绝 ACE，仅容器继承
  3. SACL 中的 Low 完整性标签（S-1-16-4096，no-write-up），可继承
  三件在同一次 SetNamedSecurityInfoW 中写入，ACE 常驻不清理。
- 创建 WRITE_RESTRICTED 受限令牌，restricting SIDs =
  [工作区 SID, 放行 SID, Everyone, Logon SID]
- 把令牌降到 Low 完整性：写入未标 Low 的对象被 no-write-up 规则拒绝，
  这是第 3 件标签存在的原因，也是纵深防御的一层
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
import stat
import struct
import subprocess
import sys
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Tuple,
)

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
_STANDARD_RIGHTS_WRITE = 0x00020000
_DELETE = 0x00010000
_FILE_DELETE_CHILD = 0x00000040
_WRITE_OWNER = 0x00080000

# 与 DSH 0.1.7 的 GRANT_MASK 逐位一致：
#   (FILE_GENERIC_WRITE & ~STANDARD_RIGHTS_WRITE) | DELETE | FILE_DELETE_CHILD
# 剔除 STANDARD_RIGHTS_WRITE（其中含 WRITE_DAC / WRITE_OWNER）：
# 受限进程若能改写 ACL 就能逃逸沙箱。
# 只授予目录，文件通过 ACE 继承获得访问权。
_GRANT_MASK = (
    (_FILE_GENERIC_WRITE & ~_STANDARD_RIGHTS_WRITE)
    | _DELETE
    | _FILE_DELETE_CHILD
)


# ── ACE / ACL 常量 ────────────────────────────────────────────────

_CONTAINER_INHERIT_ACE = 0x2
_OBJECT_INHERIT_ACE = 0x1
_ACE_INHERIT_FLAGS = _CONTAINER_INHERIT_ACE | _OBJECT_INHERIT_ACE

_ACCESS_ALLOWED_ACE_TYPE = 0x0
_ACCESS_DENIED_ACE_TYPE = 0x1
_SYSTEM_MANDATORY_LABEL_ACE_TYPE = 0x11
_SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 0x1
_ACL_REVISION = 0x2

_GRANT_ACCESS = 1
_DENY_ACCESS = 3
_REVOKE_ACCESS = 4
_TRUSTEE_IS_SID = 0
_TRUSTEE_IS_UNKNOWN = 0

_SE_FILE_OBJECT = 1
_DACL_SECURITY_INFORMATION = 0x00000004
_LABEL_SECURITY_INFORMATION = 0x00000010
_ERROR_SUCCESS = 0

# 已知 SID：Everyone 与 Low 完整性标签（S-1-16-4096）
_WORLD_SID = "S-1-1-0"
_LOW_LABEL_SID = "S-1-16-4096"


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
_TokenIntegrityLevel = 25

# 完整性 SID 在令牌中的属性标志：标记该 SID 是完整性级别而非普通组
_SE_GROUP_INTEGRITY = 0x00000020

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


class TOKEN_USER(ctypes.Structure):
    _fields_ = [
        ("User", SID_AND_ATTRIBUTES),
    ]


class ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
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

_advapi32.InitializeAcl.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD
]
_advapi32.InitializeAcl.restype = wintypes.BOOL

_advapi32.AddMandatoryAce.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, ctypes.c_void_p,
]
_advapi32.AddMandatoryAce.restype = wintypes.BOOL

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

_advapi32.ConvertSidToStringSidW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)
]
_advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

_advapi32.GetAclInformation.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int
]
_advapi32.GetAclInformation.restype = wintypes.BOOL

_advapi32.GetAce.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)
]
_advapi32.GetAce.restype = wintypes.BOOL

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


def _derive_capability_sid(seed: str) -> str:
    """由种子字符串确定性派生能力 SID。

    算法与 dsh 的 workspaceWriteSid 一致：
    sha256(种子) 前 8 字节 → 两个 30 位子权威 → S-1-4-x-y。
    同一种子永远产生同一 SID，不同种子产生不同 SID。
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    first = (struct.unpack_from("<I", digest, 0)[0] % (2**30 - 1)) + 1
    second = (struct.unpack_from("<I", digest, 4)[0] % (2**30 - 1)) + 1
    return f"S-1-4-{first}-{second}"


def workspace_write_sid(workspace_root: str) -> str:
    """派生工作区能力 SID。

    种子是规范工作区路径，因此该 SID 随 cwd 变化，换个目录运行就失效，
    不具备跨会话持久性；持久放行用 grant_write_sid。
    """
    return _derive_capability_sid(os.path.realpath(workspace_root))


def _current_user_sid_string() -> str:
    """返回当前进程令牌的用户 SID 字符串。"""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(
        _kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
    ):
        raise SandboxError(f"OpenProcessToken 失败: {ctypes.get_last_error()}")
    try:
        size = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(
            token, _TokenUser, None, 0, ctypes.byref(size)
        )
        if size.value == 0:
            raise SandboxError(
                "GetTokenInformation(TokenUser, 大小探测) 失败: "
                f"{ctypes.get_last_error()}"
            )
        buf = ctypes.create_string_buffer(size.value)
        if not _advapi32.GetTokenInformation(
            token, _TokenUser, buf, size.value, ctypes.byref(size)
        ):
            raise SandboxError(
                f"GetTokenInformation(TokenUser) 失败: {ctypes.get_last_error()}"
            )
        user = ctypes.cast(buf, ctypes.POINTER(TOKEN_USER)).contents
        sid_str = ctypes.c_wchar_p()
        if not _advapi32.ConvertSidToStringSidW(
            user.User.Sid, ctypes.byref(sid_str)
        ):
            raise SandboxError(
                f"ConvertSidToStringSidW 失败: {ctypes.get_last_error()}"
            )
        try:
            return sid_str.value or ""
        finally:
            _kernel32.LocalFree(ctypes.cast(sid_str, ctypes.c_void_p))
    finally:
        _kernel32.CloseHandle(token)


def grant_write_sid() -> str:
    """派生放行 SID：由当前用户 SID 决定，与 cwd 无关，因此跨会话持久。

    grant_write_access 把该 SID 的允许写入 ACE 写进目标目录的 DACL；
    每个会话的 restricting SID 集合都包含它，于是被放行的目录在所有
    会话中都保持可写。"""
    return _derive_capability_sid("chat2cli-grant:" + _current_user_sid_string())


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

# GetAclInformation 的信息类
_AclSizeInformation = 2

# ACE 头中的标志位：AceFlags 低 4 位是继承标志，第 5 位表示 ACE 本身是继承来的
_INHERITED_ACE = 0x10
_ACE_INHERIT_MASK = 0x0F


class _AceEntry:
    """ACL 中一条 ACE 的关键字段。

    ACCESS_ALLOWED_ACE / ACCESS_DENIED_ACE / SYSTEM_MANDATORY_LABEL_ACE
    三者的二进制布局相同（Header 4 字节、Mask 4 字节、SidStart），
    因此用同一个结构承载。
    """

    def __init__(
        self,
        ace_type: int,
        ace_flags: int,
        mask: int,
        sid_ptr: ctypes.c_void_p,
    ):
        self.ace_type = ace_type
        self.ace_flags = ace_flags
        self.mask = mask
        self.sid_ptr = sid_ptr

    @property
    def is_inherited(self) -> bool:
        return bool(self.ace_flags & _INHERITED_ACE)

    @property
    def inheritance(self) -> int:
        """继承标志位（不含 INHERITED_ACE）。"""
        return self.ace_flags & _ACE_INHERIT_MASK


def _iter_aces(p_acl: ctypes.c_void_p) -> List[_AceEntry]:
    """枚举 ACL 中的所有 ACE，返回 _AceEntry 列表。

    GetExplicitEntriesFromAclW 只返回允许/拒绝型且会丢失 ACE 头中的
    INHERITED_ACE 标志，无法区分"显式设置"与"从父项继承"，也拿不到
    完整性标签 ACE，因此这里直接按 ACE 结构解析。
    """
    if not p_acl:
        return []

    size_info = ACL_SIZE_INFORMATION()
    if not _advapi32.GetAclInformation(
        p_acl, ctypes.byref(size_info), ctypes.sizeof(size_info),
        _AclSizeInformation,
    ):
        raise SandboxError(
            f"GetAclInformation 失败: {ctypes.get_last_error()}"
        )

    entries: List[_AceEntry] = []
    for i in range(size_info.AceCount):
        ace_ptr = ctypes.c_void_p()
        if not _advapi32.GetAce(p_acl, i, ctypes.byref(ace_ptr)):
            raise SandboxError(f"GetAce({i}) 失败: {ctypes.get_last_error()}")

        # ACE_HEADER：AceType(BYTE)、AceFlags(BYTE)、AceSize(WORD)
        header = ctypes.cast(ace_ptr, ctypes.POINTER(ctypes.c_ubyte))
        ace_type = header[0]
        ace_flags = header[1]

        base = ace_ptr.value or 0
        mask = ctypes.cast(
            base + 4, ctypes.POINTER(wintypes.DWORD)
        ).contents.value
        sid_ptr = ctypes.c_void_p(base + 8)
        entries.append(_AceEntry(ace_type, ace_flags, mask, sid_ptr))
    return entries


def _exact_grant_present(
    p_dacl: ctypes.c_void_p, sid_ptr: ctypes.c_void_p
) -> bool:
    """DACL 中是否已有与 DSH 0.1.7 逐字段一致的能力 SID 允许 ACE。

    匹配条件：aceType=Allow、inheritance=OI|CI、mask=_GRANT_MASK、
    trustee=能力 SID。DSH 用严格相等判定，掩码差一位就不认，
    因此这里必须逐字段比对而非按位包含。
    """
    for entry in _iter_aces(p_dacl):
        if entry.ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            continue
        if entry.inheritance != _ACE_INHERIT_FLAGS:
            continue
        if entry.mask != _GRANT_MASK:
            continue
        if _sid_equal(entry.sid_ptr, sid_ptr):
            return True
    return False


def _exact_deny_present(
    p_dacl: ctypes.c_void_p, world_sid_ptr: ctypes.c_void_p
) -> bool:
    """DACL 中是否已有对 Everyone 的 FILE_DELETE_CHILD 拒绝 ACE。

    匹配条件：aceType=Deny、inheritance=CI（仅容器，不能继承到文件上）、
    mask=FILE_DELETE_CHILD、trustee=Everyone。
    """
    for entry in _iter_aces(p_dacl):
        if entry.ace_type != _ACCESS_DENIED_ACE_TYPE:
            continue
        if entry.inheritance != _CONTAINER_INHERIT_ACE:
            continue
        if entry.mask != _FILE_DELETE_CHILD:
            continue
        if _sid_equal(entry.sid_ptr, world_sid_ptr):
            return True
    return False


def _label_present(
    p_sacl: ctypes.c_void_p, label_sid_ptr: ctypes.c_void_p
) -> bool:
    """SACL 中是否已有 Low 完整性标签 ACE。

    匹配条件：aceType=MandatoryLabel、inheritance=OI|CI、
    policy=NO_WRITE_UP、trustee=Low 标签 SID。
    """
    for entry in _iter_aces(p_sacl):
        if entry.ace_type != _SYSTEM_MANDATORY_LABEL_ACE_TYPE:
            continue
        if entry.inheritance != _ACE_INHERIT_FLAGS:
            continue
        if entry.mask != _SYSTEM_MANDATORY_LABEL_NO_WRITE_UP:
            continue
        if _sid_equal(entry.sid_ptr, label_sid_ptr):
            return True
    return False


def _grant_ace_state(
    p_dacl: ctypes.c_void_p, sid_ptr: ctypes.c_void_p
) -> Tuple[bool, bool]:
    """返回 (是否有该 SID 的显式允许 ACE, 是否有继承而来的允许 ACE)。"""
    explicit = False
    inherited = False
    for entry in _iter_aces(p_dacl):
        if entry.ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            continue
        if not (entry.mask & _GRANT_MASK):
            continue
        if not _sid_equal(entry.sid_ptr, sid_ptr):
            continue
        if entry.is_inherited:
            inherited = True
        else:
            explicit = True
    return explicit, inherited


def _read_dacl(path: str) -> Tuple[ctypes.c_void_p, ctypes.c_void_p]:
    """读取路径的 DACL，返回 (p_sd, p_dacl)；调用方负责 LocalFree(p_sd)。"""
    p_sd, p_dacl, _p_sacl = _read_security(path)
    return p_sd, p_dacl


def _read_security(
    path: str,
) -> Tuple[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]:
    """读取路径的 DACL 与完整性标签(SACL)。

    返回 (p_sd, p_dacl, p_sacl)；调用方负责 LocalFree(p_sd)。
    p_sacl 可能为 None（该对象没有 SACL），此时视为无标签。
    """
    p_sd = ctypes.c_void_p()
    p_dacl = ctypes.c_void_p()
    p_sacl = ctypes.c_void_p()
    result = _advapi32.GetNamedSecurityInfoW(
        path, _SE_FILE_OBJECT,
        _DACL_SECURITY_INFORMATION | _LABEL_SECURITY_INFORMATION,
        None, None, ctypes.byref(p_dacl), ctypes.byref(p_sacl),
        ctypes.byref(p_sd),
    )
    if result != _ERROR_SUCCESS:
        raise SandboxError(f"GetNamedSecurityInfoW({path!r}) 失败: {result}")
    return p_sd, p_dacl, p_sacl


# ── Low 完整性标签 ACL 构造 ───────────────────────────────────────


def _build_low_label_acl(
    label_sid_ptr: ctypes.c_void_p,
) -> Any:
    """构造只含一条 Low 标签 ACE 的 SACL，返回缓冲区对象。

    返回 Python 缓冲区本身而非裸指针：SetNamedSecurityInfoW 在返回前复制
    ACL，调用期间缓冲区必须存活，由调用方持有引用。

    标签 ACL 必须独立构造后与 DACL 在**同一次** SetNamedSecurityInfoW
    调用中写入：分两次写会留下"DACL 已改、SACL 未改"的半成品状态，
    而 DSH 的幂等跳过要求三件同时成立，半成品会永久卡住。

    AddMandatoryAce 的 policy 取 NO_WRITE_UP：低于标签完整性的进程不得
    向上写入，这正是标签起隔离作用的机制。
    """
    sid_len = _advapi32.GetLengthSid(label_sid_ptr)
    # 与 DSH 的 buildLowLabelAcl 一致留出余量：ACL 头 8 字节 + ACE 头 4 字节
    # + SID，另加对齐余量，避免 AddMandatoryAce 因空间不足失败。
    acl_len = 16 + sid_len
    acl = ctypes.create_string_buffer(acl_len)
    acl_ptr = ctypes.cast(acl, ctypes.c_void_p)

    if not _advapi32.InitializeAcl(acl_ptr, acl_len, _ACL_REVISION):
        raise SandboxError(
            f"InitializeAcl(标签 ACL) 失败: {ctypes.get_last_error()}"
        )

    if not _advapi32.AddMandatoryAce(
        acl_ptr,
        _ACL_REVISION,
        _ACE_INHERIT_FLAGS,
        _SYSTEM_MANDATORY_LABEL_NO_WRITE_UP,
        label_sid_ptr,
    ):
        raise SandboxError(
            f"AddMandatoryAce 失败: {ctypes.get_last_error()}"
        )

    return acl


def _explicit_access(
    mask: int,
    mode: int,
    inheritance: int,
    sid_ptr: ctypes.c_void_p,
) -> EXPLICIT_ACCESS_W:
    """构造一条 EXPLICIT_ACCESS_W，供 SetEntriesInAclW 合并进 DACL。"""
    ea = EXPLICIT_ACCESS_W()
    ea.grfAccessPermissions = mask
    ea.grfAccessMode = mode
    ea.grfInheritance = inheritance
    ea.Trustee.TrusteeForm = _TRUSTEE_IS_SID
    ea.Trustee.TrusteeType = _TRUSTEE_IS_UNKNOWN
    ea.Trustee.ptstrName = ctypes.cast(sid_ptr, ctypes.c_void_p)
    return ea


def _has_write_owner(
    p_dacl: ctypes.c_void_p, user_sid_ptr: ctypes.c_void_p
) -> bool:
    """DACL 中是否已有该用户 SID 的 WRITE_OWNER 允许 ACE。

    只按位判断是否含 WRITE_OWNER，不要求掩码精确相等：这条 ACE 的作用
    只是让本次写入通过权限检查，无需与任何外部实现逐位对齐。
    """
    for entry in _iter_aces(p_dacl):
        if entry.ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            continue
        if not (entry.mask & _WRITE_OWNER):
            continue
        if _sid_equal(entry.sid_ptr, user_sid_ptr):
            return True
    return False


def _merge_and_apply(
    path: str,
    p_dacl: ctypes.c_void_p,
    entries: List[EXPLICIT_ACCESS_W],
    info: int,
    sacl_arg: Any,
) -> None:
    """把 entries 合并进 p_dacl 并应用，可选同时写 SACL。

    entries 为空时仍会执行应用：调用方可能只想改 SACL（标签）。info 决定
    实际写入哪些安全信息位——传 _LABEL_SECURITY_INFORMATION 而 sacl_arg
    为 None 表示**清除**现有标签。
    """
    ea_array = (EXPLICIT_ACCESS_W * len(entries))(*entries)
    new_acl = ctypes.c_void_p()
    result = _advapi32.SetEntriesInAclW(
        len(entries), ea_array, p_dacl, ctypes.byref(new_acl)
    )
    if result != _ERROR_SUCCESS:
        raise SandboxError(f"SetEntriesInAclW 失败: {result}")

    try:
        result = _advapi32.SetNamedSecurityInfoW(
            path, _SE_FILE_OBJECT, info,
            None, None, new_acl, sacl_arg,
        )
        if result != _ERROR_SUCCESS:
            raise SandboxError(
                f"SetNamedSecurityInfoW({path!r}) 失败: {result}"
            )
    finally:
        _kernel32.LocalFree(new_acl)


def _ensure_write_ace(path: str, sid_ptr: ctypes.c_void_p) -> bool:
    """确保目录具备 DSH 0.1.7 规格的三件套写入授权。

    三件指：
    1. 能力 SID 的可继承允许写入 ACE（DACL）
    2. 对 Everyone 的 FILE_DELETE_CHILD 拒绝 ACE（DACL，仅容器继承）
    3. Low 完整性标签 ACE（SACL）

    三件齐备时不做修改并返回 False，否则返回 True。判定用逐字段严格
    相等，与 DSH 的幂等跳过条件一致；掩码差一位就不算齐备，因为 DSH
    不认那个 ACE，放行会静默失效。

    写 SACL 需要 WRITE_OWNER，而目录所有者默认只有 WRITE_DAC。因此先
    单独补一条调用者的 WRITE_OWNER 允许 ACE（已存在则跳过），使操作
    自愈，无需用户手动 icacls。这一步必须独立成一次写入：权限检查用的是
    调用开始时目标已有的描述符，同一次调用里新增的 WO ACE 尚未生效。

    只设置传入目录本身，不递归子目录：可继承标志让 Windows 立即传播到
    所有已存在的子目录与文件，之后新建的子项也自动获得。若某个文件显式
    设置了受保护 DACL（不继承），则尊重它，不强行放行。
    """
    world_sid = _sid_from_string(_WORLD_SID)
    label_sid = _sid_from_string(_LOW_LABEL_SID)
    user_sid = _sid_from_string(_current_user_sid_string())
    try:
        p_sd, p_dacl, p_sacl = _read_security(path)
        try:
            grant_ok = _exact_grant_present(p_dacl, sid_ptr)
            deny_ok = _exact_deny_present(p_dacl, world_sid)
            label_ok = _label_present(p_sacl, label_sid)
            if grant_ok and deny_ok and label_ok:
                return False
            wo_ok = _has_write_owner(p_dacl, user_sid)
        finally:
            _kernel32.LocalFree(p_sd)

        # 前置步骤：补齐 WRITE_OWNER。没有它，下一步写 SACL 会以
        # ERROR_ACCESS_DENIED(5) 失败。
        if not wo_ok:
            p_sd, p_dacl, _p_sacl = _read_security(path)
            try:
                _merge_and_apply(
                    path, p_dacl,
                    [
                        _explicit_access(
                            _WRITE_OWNER, _GRANT_ACCESS,
                            _ACE_INHERIT_FLAGS, user_sid,
                        )
                    ],
                    _DACL_SECURITY_INFORMATION, None,
                )
            finally:
                _kernel32.LocalFree(p_sd)

        # 主体：重新读取（上一步已改变 DACL），写入三件套。
        p_sd, p_dacl, p_sacl = _read_security(path)
        try:
            grant_ok = _exact_grant_present(p_dacl, sid_ptr)
            deny_ok = _exact_deny_present(p_dacl, world_sid)
            label_ok = _label_present(p_sacl, label_sid)

            entries: List[EXPLICIT_ACCESS_W] = []
            if not grant_ok:
                # 先撤销该 SID 的既有 ACE 再重新授予：旧版本写入的掩码与
                # 0.1.7 不同，直接 GRANT 会与之合并成一个仍不精确的掩码。
                entries.append(
                    _explicit_access(0, _REVOKE_ACCESS, 0, sid_ptr)
                )
                entries.append(
                    _explicit_access(
                        _GRANT_MASK, _GRANT_ACCESS, _ACE_INHERIT_FLAGS,
                        sid_ptr,
                    )
                )
            if not deny_ok:
                entries.append(
                    _explicit_access(
                        _FILE_DELETE_CHILD, _DENY_ACCESS,
                        _CONTAINER_INHERIT_ACE, world_sid,
                    )
                )

            # 标签已存在时只传 DACL 信息：带上 LABEL 位会以传入的 pSacl
            # 整体替换现有 SACL，把已有标签清掉。
            info = _DACL_SECURITY_INFORMATION
            sacl_arg: Any = None
            if not label_ok:
                label_acl = _build_low_label_acl(label_sid)
                info |= _LABEL_SECURITY_INFORMATION
                sacl_arg = ctypes.cast(label_acl, ctypes.c_void_p)

            _merge_and_apply(path, p_dacl, entries, info, sacl_arg)
            return True
        finally:
            _kernel32.LocalFree(p_sd)
    finally:
        _kernel32.LocalFree(world_sid)
        _kernel32.LocalFree(label_sid)
        _kernel32.LocalFree(user_sid)


def _has_foreign_grant(
    p_dacl: ctypes.c_void_p, sid_ptr: ctypes.c_void_p
) -> bool:
    """DACL 中是否存在**其他**能力 SID 的精确授予 ACE。

    用于撤销时决定是否清除 Low 标签：同一目录可能承载多个能力授予
    （例如工作区 SID 与放行 SID），清掉标签会让仍然有效的那一个失去
    隔离语义。判定与 DSH 的 hasForeignGrant 一致：mask 精确等于
    _GRANT_MASK 且 SID 不是被撤销的那个。
    """
    for entry in _iter_aces(p_dacl):
        if entry.ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            continue
        if entry.mask != _GRANT_MASK:
            continue
        if _sid_equal(entry.sid_ptr, sid_ptr):
            continue
        return True
    return False


def _remove_write_ace(path: str, sid_ptr: ctypes.c_void_p) -> bool:
    """移除路径上该能力 SID 的 ACE，必要时清除 Low 标签。

    返回是否发生变更。没有该 SID 的 ACE 时不做修改并返回 False，因此
    重复撤销是幂等的。

    与 DSH 0.1.7 的 revokeWrite 一致：用 REVOKE_ACCESS 删除该 SID 的
    全部 ACE（其余条目原样保留），并且仅当目录上不再有其他能力授予时
    才清除 Low 标签——同一目录可能承载多个能力授予，留下标签是让仍
    有效的那一个继续正常工作所必需的。

    继承 ACE 无法在此移除：它由父项派生，父项撤销后自动消失。
    """
    user_sid = _sid_from_string(_current_user_sid_string())
    try:
        p_sd, p_dacl = _read_dacl(path)
        try:
            if not p_dacl:
                return False

            explicit, _inherited = _grant_ace_state(p_dacl, sid_ptr)
            # 该 SID 无 ACE 时不触碰描述符：避免为无谓的写操作重传播整棵树
            if not explicit:
                return False

            # 若接下来要清标签，同样需要 WRITE_OWNER（标签在 SACL）。
            # 与 grant 一样必须独立成一次写入，新加的 WO ACE 才能生效。
            keep_label = _has_foreign_grant(p_dacl, sid_ptr)
            need_wo = (
                not keep_label and not _has_write_owner(p_dacl, user_sid)
            )
        finally:
            _kernel32.LocalFree(p_sd)

        if need_wo:
            p_sd, p_dacl = _read_dacl(path)
            try:
                _merge_and_apply(
                    path, p_dacl,
                    [
                        _explicit_access(
                            _WRITE_OWNER, _GRANT_ACCESS,
                            _ACE_INHERIT_FLAGS, user_sid,
                        )
                    ],
                    _DACL_SECURITY_INFORMATION, None,
                )
            finally:
                _kernel32.LocalFree(p_sd)

        p_sd, p_dacl = _read_dacl(path)
        try:
            # 仍有其他能力授予时保留标签（kind=keep → information=4）；
            # 否则连标签一起清掉（kind=clear → information=20 且 SACL 传
            # NULL）。与 DSH 一致：清除是无条件的，不先判断标签是否存在。
            keep_label = _has_foreign_grant(p_dacl, sid_ptr)
            info = _DACL_SECURITY_INFORMATION
            if not keep_label:
                info |= _LABEL_SECURITY_INFORMATION

            _merge_and_apply(
                path, p_dacl,
                [_explicit_access(0, _REVOKE_ACCESS, 0, sid_ptr)],
                info, None,
            )
            return True
        finally:
            _kernel32.LocalFree(p_sd)
    finally:
        _kernel32.LocalFree(user_sid)


def _is_reparse_point(path: str) -> bool:
    """路径是否为 reparse point（symlink / junction）。

    这类目录指向别处，对其设置 ACL 会作用到目标上，因此递归时剪枝。
    """
    try:
        attrs = os.lstat(path).st_file_attributes
    except OSError:
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _walk_tree(root: str) -> Iterator[Tuple[str, bool]]:
    """产出 (路径, 是否目录)，覆盖 root 及其下所有已有子项。

    reparse point（symlink / junction）会被剪枝：对它设置 ACL 会作用到
    目标上，从而越出放行范围。父项先于子项产出。
    """
    yield root, True
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if not _is_reparse_point(os.path.join(dirpath, d))
        ]
        for name in dirnames:
            yield os.path.join(dirpath, name), True
        for name in filenames:
            target = os.path.join(dirpath, name)
            if not _is_reparse_point(target):
                yield target, False


class TreeOpResult(NamedTuple):
    """目录树放行/撤销操作的结果。"""

    scanned: int
    """扫描到的条目数。"""

    changed: int
    """实际发生 ACL 变更的条目数，不含扫描到但无需处理的条目。"""

    failures: List[str]
    """处理失败的条目及原因。"""


def _remove_from_tree(root: str) -> TreeOpResult:
    """清除目录树中所有显式 ACE，返回操作结果。

    单个条目失败不中止整棵树：继续处理其余条目并汇总失败，避免留下
    "改了一半却只报一条错"的不可知状态。

    目录与文件都处理：目录的显式 ACE 撤销后子项继承的 ACE 自动消失，
    但子项上单独设置过的显式 ACE（用户可能分别放行过子目录）不受影响，
    必须逐项清除，否则父目录撤销后这些子项在沙箱内依然可写。
    """
    sid_ptr = _sid_from_string(grant_write_sid())
    try:
        scanned = 0
        changed = 0
        failures: List[str] = []
        for target, _is_dir in _walk_tree(root):
            scanned += 1
            try:
                if _remove_write_ace(target, sid_ptr):
                    changed += 1
            except SandboxError as e:
                failures.append(f"{target}: {e}")
        return TreeOpResult(scanned, changed, failures)
    finally:
        _kernel32.LocalFree(sid_ptr)


def grant_write_access(path: str) -> TreeOpResult:
    """放行目录的沙箱写入权限。

    只对目标目录本身设置一条可继承 ACE：显式设置使该目录独立于父目录，
    可继承则让子项自动获得访问权，无需逐个处理。目标已在放行范围内
    （显式 ACE 或从父目录继承）时不做任何修改。ACE 常驻不清理，撤销用
    revoke_write_access。
    """
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        raise SandboxError(f"目录不存在: {root}")

    sid_ptr = _sid_from_string(grant_write_sid())
    try:
        try:
            changed = _ensure_write_ace(root, sid_ptr)
        except SandboxError as e:
            return TreeOpResult(1, 0, [f"{root}: {e}"])
        return TreeOpResult(1, 1 if changed else 0, [])
    finally:
        _kernel32.LocalFree(sid_ptr)


def revoke_write_access(path: str) -> TreeOpResult:
    """递归撤销目录的沙箱写入权限。

    目录与文件都处理。目录上的显式 ACE 撤销后，其子项继承的 ACE 自动
    消失；但子项上单独设置过的显式 ACE 不受父项影响。用户可能分别放行
    过子目录，再撤销父目录时期望整棵树都不可写，因此必须逐项清除，
    否则这些子项在沙箱内依然可写。
    """
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        raise SandboxError(f"目录不存在: {root}")
    return _remove_from_tree(root)


def grant_status(path: str) -> Dict[str, Any]:
    """检查目录树的放行状态，返回状态字典。

    "已放行"的口径是 0.1.7 三件套齐备（能力 ACE + world deny + Low 标签）：
    只看能力 ACE 会把无效放行报告成已放行——这正是升级后最常见的误判，
    旧的 ACE 还在，但缺标签导致写入被完整性检查拒绝。

    explicit_entries 列出树中带显式能力 ACE 的条目：它们不依赖父目录，
    因此父目录撤销后依然有 ACE，是判断"撤销是否彻底"的依据。
    只读操作，不修改任何 ACL。
    """
    root = os.path.abspath(path)
    if not os.path.isdir(root):
        raise SandboxError(f"目录不存在: {root}")

    sid_ptr = _sid_from_string(grant_write_sid())
    world_sid_ptr = _sid_from_string(_WORLD_SID)
    label_sid_ptr = _sid_from_string(_LOW_LABEL_SID)
    try:
        explicit_entries: List[str] = []
        writable_count = 0
        total_count = 0
        failures: List[str] = []
        root_state: Dict[str, bool] = {
            "grant": False, "deny": False, "label": False,
        }

        for target, _is_dir in _walk_tree(root):
            total_count += 1
            try:
                p_sd, p_dacl, p_sacl = _read_security(target)
            except SandboxError as e:
                failures.append(f"{target}: {e}")
                continue
            try:
                explicit, _inherited = _grant_ace_state(p_dacl, sid_ptr)
                state = {
                    "grant": _exact_grant_present(p_dacl, sid_ptr),
                    "deny": _exact_deny_present(p_dacl, world_sid_ptr),
                    "label": _label_present(p_sacl, label_sid_ptr),
                }
            finally:
                _kernel32.LocalFree(p_sd)

            if explicit:
                explicit_entries.append(target)
            if state["grant"] and state["deny"] and state["label"]:
                writable_count += 1
            if target == root:
                root_state = state

        return {
            "path": root,
            "root_grant": root_state["grant"],
            "root_deny": root_state["deny"],
            "root_label": root_state["label"],
            "root_granted": (
                root_state["grant"]
                and root_state["deny"]
                and root_state["label"]
            ),
            "explicit_entries": explicit_entries,
            "writable_count": writable_count,
            "total_count": total_count,
            "failures": failures,
        }
    finally:
        _kernel32.LocalFree(sid_ptr)
        _kernel32.LocalFree(world_sid_ptr)
        _kernel32.LocalFree(label_sid_ptr)


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


def _set_token_low_integrity(
    token: wintypes.HANDLE, label_sid_ptr: ctypes.c_void_p
) -> None:
    """把令牌的完整性级别设为 Low（S-1-16-4096）。

    与 DSH 的沙箱模型一致：沙箱子进程运行在 Low 完整性，写入未标 Low 的
    对象会被 no-write-up 规则拒绝。这是纵深防御的一层——即使某个目录被
    误授予了能力 SID，只要它没有 Low 标签，沙箱进程依然写不进去。

    代价是被授权的目录必须显式标上 Low 标签，否则写入会因完整性检查
    失败（这正是 _ensure_write_ace 写标签的原因）。

    TokenIntegrityLevel 的载荷是单条 SID_AND_ATTRIBUTES，属性必须带
    SE_GROUP_INTEGRITY，否则 SetTokenInformation 以参数错误失败。
    """
    label = SID_AND_ATTRIBUTES()
    label.Sid = ctypes.cast(label_sid_ptr, ctypes.c_void_p)
    label.Attributes = _SE_GROUP_INTEGRITY
    if not _advapi32.SetTokenInformation(
        token, _TokenIntegrityLevel, ctypes.byref(label),
        ctypes.sizeof(label),
    ):
        raise SandboxError(
            f"SetTokenInformation(TokenIntegrityLevel) 失败: "
            f"{ctypes.get_last_error()}"
        )


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
    # 必须加 -OutputFormat Text：EncodedCommand 模式下 PowerShell 会把
    # stderr 上的错误记录序列化成 CLIXML（#< CLIXML ... <Objs>）而非纯文本，
    # 污染读取端；Text 强制纯文本且不影响 stdout 渲染。
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    popen = subprocess.Popen(
        ["pwsh.exe", "-NoProfile", "-OutputFormat", "Text", "-EncodedCommand", encoded],
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

    # 1b. 派生放行 SID。它与 cwd 无关，因此在所有会话中取值相同，
    # 使 grant_write_access 放行的目录在每个会话都保持可写。
    grant_sid = _sid_from_string(grant_write_sid())

    # 2. 获取 Everyone SID 与 Low 完整性标签 SID
    everyone_sid = _sid_from_string(_WORLD_SID)
    low_label_sid = _sid_from_string(_LOW_LABEL_SID)

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

        # 4. 确保工作目录具备三件套授权（能力 ACE + world deny + Low 标签）。
        # 必须在令牌降完整性之前完成：这是沙箱外身份的 ACL 编辑。
        _ensure_write_ace(cwd_abs, ws_sid)

        # 5. 创建受限令牌。restricting SID 是白名单：对象 DACL 必须授予
        # 其中至少一个 SID 访问权，操作才被放行。grant_sid 入列后，
        # 被 grant_write_access 放行过的目录在本会话同样可写。
        restricted_token = _create_restricted_token(
            current_token,
            [ws_sid, grant_sid, everyone_sid, logon_sid],
        )

        # 5b. 把工作区与放行 SID 的允许 ACE 合并进受限令牌的默认 DACL。
        # 缺少这一步时，子进程创建标准流管道会被 pass-2 写入检查拒绝，
        # 表现为 CreateProcessAsUserW 返回 ERROR_ACCESS_DENIED (5)。
        _set_token_default_dacl_grant(restricted_token, ws_sid)
        _set_token_default_dacl_grant(restricted_token, grant_sid)

        # 5c. 把令牌降到 Low 完整性，与 DSH 的沙箱模型一致。
        # 必须放在 _ensure_write_ace 之后：写标签需要提升前的令牌权限，
        # 而 _ensure_write_ace 是沙箱外身份执行的 ACL 编辑。
        _set_token_low_integrity(restricted_token, low_label_sid)

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
                # 必须加 -OutputFormat Text：EncodedCommand 模式下 PowerShell
                # 会把 stderr 上的错误记录序列化成 CLIXML（#< CLIXML ... <Objs>）
                # 而非纯文本，污染读取端；Text 强制纯文本且不影响 stdout 渲染。
                encoded = base64.b64encode(
                    command.encode("utf-16-le")
                ).decode("ascii")
                cmdline = ctypes.create_unicode_buffer(
                    f"pwsh.exe -NoProfile -OutputFormat Text -EncodedCommand {encoded}"
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
        _kernel32.LocalFree(grant_sid)
        _kernel32.LocalFree(everyone_sid)
        _kernel32.LocalFree(low_label_sid)
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
                f"({os.getcwd()})。如需写入其他目录，请在沙箱外运行 "
                "`chat2cli.py sandbox grant <目录>` 持久放行该目录，或在对应目录下 "
                "重新运行 chat2cli，或使用 --danger-full-access 关闭沙箱。"
            )
    return None

