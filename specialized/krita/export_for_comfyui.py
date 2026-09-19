
# -*- coding: utf-8 -*-
"""
Krita 脚本：把当前文档导出并复制到剪贴板，供 ComfyUI 使用

用途：
  ComfyUI 自带的 Mask Editor 不好用，也无法吸色。在 Krita 里画好内容后，
  用本脚本一键导出并复制，切到 ComfyUI 直接粘贴。

  内容可以是 mask，也可以是普通彩图——后者没有需要保留的透明区域，
  导出结果同样正确。

用法（二选一）：
  1. 工具 > 脚本 > 常用脚本快捷键（Ten Scripts）：把本 .py 绑定到某个槽位，
     为该槽位对应的 "Execute Script N" 分配快捷键。脚本入口是 main()。
  2. 工具 > 脚本 > 脚本调试工具（Scripter）中：
       import sys
       sys.path.append(r"C:\\Workspaces\\scripts\\specialized\\krita")
       from export_for_comfyui import export_and_copy
       export_and_copy()

导出完成后会尝试自动切回 ComfyUI 窗口，成功则不再打扰；找不到窗口或切换
失败时才弹框提示。

关键原理：
  遮罩类内容的有效数据常常落在完全透明区域（例如整幅图只有一小块不透明，
  其余是 alpha=0 的纯色）。而 Krita 的合成/导出流程会把完全透明区域的 RGB
  清零，这是其合成引擎的既定行为，任何依赖 rootNode().save() 或
  exportImage() 的路径都无法绕开，导致这些数据丢失。

  本脚本完全绕过 Krita 的合成与编码：
    1. 直接读颜料层的 pixelData()——图层自身的原始像素，不受蒙版/合成影响，
       透明区域的 RGB 依然存在于此。
    2. 直接读透明蒙版的 pixelData()——1 字节/像素的 Alpha。
    3. 用 Python 拼出 RGBA 后自行写出文件。透明区域的 RGB 原样保留，不被清零。

适用范围：
  单个颜料层 + 可选一个透明度蒙版子节点，颜色模型 RGBA、深度 U8（8 位/通道）。
  其他结构会抛异常而不是静默退化。
"""

import os
import time
import zlib
import struct
import ctypes
import tempfile

from ctypes import wintypes

from krita import Krita, Extension
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox


# ---------------------------------------------------------------------------
# Windows 剪贴板：把文件复制到剪贴板（等价于资源管理器 Ctrl+C 一个文件）
# ---------------------------------------------------------------------------

CF_UNICODETEXT = 13
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

# Windows 句柄在 64 位下是 64 位指针。ctypes 不声明 argtypes/restype 时默认按
# 32 位 int 传递，会把句柄截断并抛 "int too long to convert"。必须显式声明。
_kernel32 = ctypes.windll.kernel32
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint32, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype = ctypes.c_bool
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.restype = ctypes.c_void_p
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

_user32 = ctypes.windll.user32
_user32.OpenClipboard.argtypes = [ctypes.c_void_p]
_user32.OpenClipboard.restype = ctypes.c_bool
_user32.EmptyClipboard.restype = ctypes.c_bool
_user32.CloseClipboard.restype = ctypes.c_bool
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p


class DROPFILES(ctypes.Structure):
    # Windows DROPFILES 结构体，总长固定 20 字节：
    #   DWORD pFiles (4) + POINT pt (8) + BOOL fNC (4) + BOOL fWide (4)
    # 关键：BOOL 是 4 字节 int，不是 ctypes.c_bool（1 字节）。用 c_bool 会让
    # 结构体缩到 16 字节，fWide 落到偏移 13 而非 Windows 期望的 16，Windows
    # 会把路径数据的字节误读成 fWide，行为不确定。
    _fields_ = [
        ("pFiles", ctypes.c_uint32),
        ("pt_x", ctypes.c_int32),
        ("pt_y", ctypes.c_int32),
        ("fNC", ctypes.c_int32),
        ("fWide", ctypes.c_int32),
    ]


def _build_dropfiles(paths):
    """构造 CF_HDROP 负载：DROPFILES 头 + UTF-16LE 空终止路径列表 + 末尾双 NULL。"""
    header = DROPFILES()
    header.pFiles = ctypes.sizeof(DROPFILES)  # = 20
    header.fWide = 1
    buf = ctypes.string_at(ctypes.byref(header), ctypes.sizeof(header))
    for p in paths:
        buf += os.path.abspath(p).encode("utf-16-le") + b"\x00\x00"
    buf += b"\x00\x00"
    return buf


def _set_clipboard_format(fmt, data):
    """
    分配全局内存并写入指定剪贴板格式。

    成功后 HGLOBAL 所有权归系统，不能再释放；失败时释放并返回 False。
    """
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    if not h:
        return False
    ptr = _kernel32.GlobalLock(h)
    if not ptr:
        _kernel32.GlobalFree(h)
        return False
    try:
        ctypes.memmove(ptr, data, len(data))
    finally:
        _kernel32.GlobalUnlock(h)
    if not _user32.SetClipboardData(fmt, h):
        _kernel32.GlobalFree(h)
        return False
    return True


def copy_file_to_clipboard(file_path):
    """
    把磁盘上的文件复制到 Windows 剪贴板。

    同时写入两种格式：
      - CF_HDROP：文件列表。资源管理器、支持「粘贴文件」的应用拿到文件本身。
      - CF_UNICODETEXT：绝对路径文本。只读剪贴板文本的前端（如浏览器）能拿到路径。
    """
    abs_path = os.path.abspath(file_path)
    text_blob = (abs_path + "\x00").encode("utf-16-le")
    drop_blob = _build_dropfiles([abs_path])

    last_error = None
    # 剪贴板是全局共享资源，可能被其他进程瞬时占用，失败时重试。
    for _ in range(30):
        if not _user32.OpenClipboard(None):
            last_error = RuntimeError("OpenClipboard 失败")
            time.sleep(0.1)
            continue
        if not _user32.EmptyClipboard():
            _user32.CloseClipboard()
            last_error = RuntimeError("EmptyClipboard 失败")
            time.sleep(0.1)
            continue

        ok = _set_clipboard_format(CF_UNICODETEXT, text_blob)
        if ok:
            ok = _set_clipboard_format(CF_HDROP, drop_blob)
        _user32.CloseClipboard()

        if not ok:
            raise RuntimeError("SetClipboardData 失败")
        return

    raise last_error or RuntimeError("剪贴板写入失败")


# ---------------------------------------------------------------------------
# 窗口激活：导出后切回 ComfyUI
# ---------------------------------------------------------------------------

# 匹配窗口标题的子串（不区分大小写）。ComfyUI 在 Firefox 中作为独立窗口打开时，
# 标题形如 "*Unsaved Workflow (6) - ComfyUI — Mozilla Firefox 中的 ComfyUI"。
COMFYUI_WINDOW_TITLE_SUBSTRING = "ComfyUI"

# 激活 ComfyUI 前的延迟（毫秒）。Ten Scripts 在 main() 返回后还会在 Krita 窗口上
# 显示浮动通知，把 Krita 重新提到前台。推迟激活可确保它发生在 Krita 收尾之后。
ACTIVATION_DELAY_MS = 300

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

_user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
_user32.EnumWindows.restype = ctypes.c_bool
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.IsWindowVisible.restype = ctypes.c_bool
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = ctypes.c_bool
_user32.IsIconic.argtypes = [wintypes.HWND]
_user32.IsIconic.restype = ctypes.c_bool
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = ctypes.c_bool
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, ctypes.c_bool]
_user32.AttachThreadInput.restype = ctypes.c_bool
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.BringWindowToTop.restype = ctypes.c_bool

_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _find_window_by_title(substring):
    """返回标题含指定子串（不区分大小写）的第一个可见顶层窗口句柄；找不到返回 None。"""
    matches = []

    @WNDENUMPROC
    def _enum_proc(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        if substring.lower() in buf.value.lower():
            matches.append(hwnd)
        return True

    _user32.EnumWindows(_enum_proc, 0)
    return matches[0] if matches else None


def _activate_window(hwnd):
    """
    把窗口切到前台并激活，成功返回 True。

    只在窗口最小化时调用 ShowWindow(SW_RESTORE)：SW_RESTORE 的语义是「恢复到
    原始尺寸和位置」，对已最大化的窗口调用会把它还原成最大化之前的大小。
    非最小化的窗口保持原样，不做任何 ShowWindow。

    SetForegroundWindow 受前台锁限制：只有调用进程已是前台进程时才一定成功。
    脚本由用户在 Krita 中按快捷键触发，此刻 Krita 正持前台，通常直接成功。
    若失败，回退到 AttachThreadInput——把本线程的输入队列临时接到当前前台线程上，
    绕过前台锁再试一次。
    """
    if _user32.IsIconic(hwnd):
        SW_RESTORE = 9
        _user32.ShowWindow(hwnd, SW_RESTORE)

    if _user32.SetForegroundWindow(hwnd):
        return True

    foreground = _user32.GetForegroundWindow()
    if foreground:
        fg_thread = _user32.GetWindowThreadProcessId(foreground, None)
        cur_thread = _kernel32.GetCurrentThreadId()
        if fg_thread and fg_thread != cur_thread:
            _user32.AttachThreadInput(cur_thread, fg_thread, True)
            try:
                _user32.SetForegroundWindow(hwnd)
            finally:
                _user32.AttachThreadInput(cur_thread, fg_thread, False)

    _user32.BringWindowToTop(hwnd)
    return _user32.GetForegroundWindow() == hwnd


def _activate_comfyui_or_warn(export_path):
    """
    查找并激活 ComfyUI 窗口。

    成功则静默结束；找不到窗口或激活失败时弹框告知，因为此时用户需要手动
    切换才能粘贴。
    """
    hwnd = _find_window_by_title(COMFYUI_WINDOW_TITLE_SUBSTRING)
    if hwnd is None:
        QMessageBox.information(
            None,
            "完成",
            f"已导出并复制到剪贴板：\n{export_path}\n\n"
            f"未找到 {COMFYUI_WINDOW_TITLE_SUBSTRING} 窗口，请手动切换后粘贴。",
        )
        return
    if not _activate_window(hwnd):
        QMessageBox.information(
            None,
            "完成",
            f"已导出并复制到剪贴板：\n{export_path}\n\n"
            f"无法切换到 {COMFYUI_WINDOW_TITLE_SUBSTRING} 窗口，请手动切换后粘贴。",
        )


# ---------------------------------------------------------------------------
# PNG 手写：完全绕过 Krita 的合成引擎
# ---------------------------------------------------------------------------

def _png_chunk(chunk_type, data):
    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xffffffff
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)


def _write_png(path, width, height, rgba, dpi=None):
    """
    写出 8 位 RGBA PNG。透明区域的 RGB 值原样写入，不做任何清零。

    参数：
        path:   输出路径
        width:  宽度（像素）
        height: 高度（像素）
        rgba:   RGBA 字节串，长度 width * height * 4
        dpi:    可选，写入 pHYs 块的 DPI
    """
    # IHDR: width, height, bit_depth=8, color_type=6(RGBA), compression=0,
    #       filter=0, interlace=0
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    # 每条扫描线前置一个 filter 字节（0 = None），其余为像素数据
    stride = width * 4
    lines = [b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height)]
    raw = b"".join(lines)

    compressed = zlib.compress(raw, 6)

    chunks = [_png_chunk(b"IHDR", ihdr)]
    if dpi:
        ppm = int(dpi * 39.3701)  # 每米像素数
        chunks.append(_png_chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1)))
    chunks.append(_png_chunk(b"IDAT", compressed))
    chunks.append(_png_chunk(b"IEND", b""))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        for c in chunks:
            f.write(c)


def export_preserving_transparent_rgb(doc, export_path):
    """
    导出文档为 PNG，保留透明区域的原始 RGB 数据。

    前提：文档结构为单个颜料层（可选一个透明度蒙版子节点），
    颜色模型 RGBA、深度 U8。
    """
    w, h = doc.width(), doc.height()
    root = doc.rootNode()

    paint_layers = [n for n in root.childNodes() if n.type() == "paintlayer"]
    if not paint_layers:
        raise RuntimeError("文档中没有颜料层")
    if len(paint_layers) > 1:
        raise RuntimeError(
            f"文档中有 {len(paint_layers)} 个颜料层，本脚本只支持单颜料层。"
            "请先合并图层，或修改脚本以支持多图层。"
        )

    paint_layer = paint_layers[0]

    if paint_layer.colorModel() != "RGBA" or paint_layer.colorDepth() != "U8":
        raise RuntimeError(
            f"颜料层为 {paint_layer.colorModel()}/{paint_layer.colorDepth()}，"
            "本脚本仅支持 RGBA/U8。"
        )

    transparency_mask = None
    for n in paint_layer.childNodes():
        if n.type() == "transparencymask":
            transparency_mask = n
            break

    # ---- 取颜料层原始像素（Krita 内部为 BGRA 字节序） ----
    ld = bytes(paint_layer.pixelData(0, 0, w, h))
    expected = w * h * 4
    if len(ld) != expected:
        raise RuntimeError(
            f"颜料层像素数据长度异常：{len(ld)}，期望 {expected}。"
        )

    # ---- 取透明蒙版 Alpha（1 字节/像素） ----
    md = None
    if transparency_mask is not None:
        md = bytes(transparency_mask.pixelData(0, 0, w, h))
        if len(md) != w * h:
            raise RuntimeError(
                f"透明蒙版数据长度异常：{len(md)}，期望 {w * h}。"
            )

    # ---- BGRA -> RGBA：交换每个像素的第 0 字节和第 2 字节 ----
    rgba = bytearray(ld)
    rgba[0::4], rgba[2::4] = rgba[2::4], rgba[0::4]

    # ---- 合并 Alpha：最终 alpha = 图层 alpha × 蒙版 alpha / 255 ----
    # 透明区域（蒙版 alpha=0）的 RGB 保持颜料层原值，不被清零。
    if md is not None:
        layer_a = bytes(rgba[3::4])
        rgba[3::4] = bytes((a * m) // 255 for a, m in zip(layer_a, md))

    _write_png(export_path, w, h, bytes(rgba), dpi=doc.resolution())


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------

def export_and_copy():
    """导出当前活动文档为 PNG（保留透明区域 RGB），并复制文件到剪贴板。"""
    app = Krita.instance()
    doc = app.activeDocument()
    if not doc:
        QMessageBox.warning(None, "导出", "没有打开的文档。")
        return None

    doc.waitForDone()

    doc_name = os.path.splitext(os.path.basename(doc.fileName() or "untitled"))[0]
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    # 前缀标明文件由本脚本导出（保留透明区 RGB），便于在临时目录中识别
    filename = f"krita_export_{doc_name}_{timestamp}.png"
    export_path = os.path.join(tempfile.gettempdir(), filename)

    try:
        export_preserving_transparent_rgb(doc, export_path)
    except Exception as e:
        QMessageBox.critical(None, "导出失败", str(e))
        return None

    if not os.path.exists(export_path):
        QMessageBox.critical(None, "导出失败", "PNG 文件未生成。")
        return None

    try:
        copy_file_to_clipboard(export_path)
    except Exception as e:
        QMessageBox.warning(
            None,
            "剪贴板",
            f"文件已导出到：\n{export_path}\n\n但复制到剪贴板失败：\n{e}",
        )
        return export_path

    # ---- 切回 ComfyUI ----
    # Ten Scripts 在 main() 返回后还会在 Krita 窗口上显示浮动通知，把 Krita
    # 重新提到前台，覆盖刚做的窗口激活。因此把激活推迟到事件循环空闲后执行，
    # 确保它发生在 Krita 的收尾动作之后。
    QTimer.singleShot(ACTIVATION_DELAY_MS, lambda: _activate_comfyui_or_warn(export_path))
    return export_path


def main():
    """
    Ten Scripts 入口。

    Ten Scripts 通过 importlib 加载本文件后，会查找并调用名为 main 的可调用对象。
    """
    return export_and_copy()


# ---------------------------------------------------------------------------
# Krita 插件入口
# ---------------------------------------------------------------------------

class ExportPreserveAlphaExtension(Extension):
    """在 Tools > Scripts 中添加菜单项。"""

    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "export_for_comfyui",
            "导出并复制到剪贴板（供 ComfyUI 使用）",
            "tools/scripts",
        )
        action.triggered.connect(export_and_copy)


# 仅当作为 Krita 插件（pykrita 目录）加载时注册扩展。
# Ten Scripts 以固定模块名 "users_script" 加载本文件，此时不注册，
# 避免每次触发快捷键都重复添加一次扩展。
if __name__ != "users_script":
    Krita.instance().addExtension(ExportPreserveAlphaExtension(Krita.instance()))
