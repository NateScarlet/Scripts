
# -*- coding: utf-8 -*-
"""
Krita 脚本：把当前文档导出并复制到剪贴板，供 ComfyUI 使用

用途：
  ComfyUI 自带的 Mask Editor 不好用，也无法吸色。在 Krita 里画好内容后，
  用本脚本一键导出并复制，切到 ComfyUI 直接粘贴。

用法（二选一）：
  1. 工具 > 脚本 > 常用脚本快捷键（Ten Scripts）：把本 .py 绑定到某个槽位，
     为该槽位对应的 "Execute Script N" 分配快捷键。脚本入口是 main()。
  2. 工具 > 脚本 > 脚本调试工具（Scripter）中：
       import sys
       sys.path.append(r"C:\\Workspaces\\scripts\\specialized\\krita")
       from export_for_comfyui import export_and_copy
       export_and_copy()

导出完成后会把当前文档对应原图内嵌的 ComfyUI 工作流送达网页端打开，并切到
ComfyUI 窗口，省去手动打开工作流和切换窗口这两步。该功能复用 image-funnel
已部署的 open_workflow 钩子（目录由 IMAGE_FUNNEL_HOOK_DIR 指定，未设置时回退到
%AppData%\\io.github.NateScarlet.image-funnel\\hooks），以 `uv run` 启动，因此需要 uv 在 PATH 中；
窗口激活与确认也由该钩子完成，本脚本不再枚举窗口。钩子目录或 uv 缺失、
原图未保存到磁盘、原图没有内嵌工作流等情况下只提示，不影响导出与剪贴板复制。

导出成功后会把文档标记为「未修改」，这样关闭 Krita 时不会再弹「是否保存」
确认。注意：导出写的是临时目录中的副本，原文档的改动并没有写回原文件，
该标记会一并取消 Krita 对未保存编辑的保护。

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
"""

import json
import os
import time
import zlib
import struct
import ctypes
import shutil
import subprocess
import tempfile
from krita import Krita
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

# 调用钩子前的延迟（毫秒）。Ten Scripts 在 main() 返回后还会在 Krita 窗口上
# 显示浮动通知，把 Krita 重新提到前台。推迟调用可确保钩子内的窗口激活
# 发生在 Krita 收尾之后。
ACTIVATION_DELAY_MS = 300


# ---------------------------------------------------------------------------
# 送达工作流：复用 image-funnel 已部署的 open_workflow 钩子
# ---------------------------------------------------------------------------

# 钩子部署目录的环境变量名（与 image-funnel 自身保持一致）
HOOK_DIR_ENV_VAR = "IMAGE_FUNNEL_HOOK_DIR"


# image-funnel 默认部署位置中的应用目录名（反向域名，与其应用标识一致）
IMAGE_FUNNEL_APP_DIR = "io.github.NateScarlet.image-funnel"


def _resolve_hooks_dir():
    """
    解析钩子部署目录：优先 IMAGE_FUNNEL_HOOK_DIR，未设置时回退到 image-funnel
    的默认部署位置（%AppData%\\io.github.NateScarlet.image-funnel\\hooks）。
    """
    configured = os.environ.get(HOOK_DIR_ENV_VAR, "").strip()
    if configured:
        return configured

    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        return ""
    return os.path.join(appdata, IMAGE_FUNNEL_APP_DIR, "hooks")


def _last_line(text):
    """取文本最后一行非空内容，用于把钩子的 traceback 收敛成一句原因。"""
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _warn_open_workflow(reason):
    """送达工作流失败时的统一提示。导出本身已经成功，因此只作为附加说明。"""
    QMessageBox.information(
        None,
        "打开工作流",
        f"未能自动打开原图的工作流：\n\n{reason}\n\n请手动切换到 ComfyUI 窗口。",
    )


def _open_embedded_workflow_or_warn(image_path):
    """
    把原图内嵌的 ComfyUI 工作流送达网页端打开。

    复用 image-funnel 已部署的 open_workflow 钩子，与「在 ComfyUI 页面打开」
    快捷键走同一条路径。通过 uv 启动，因此需要 uv 在 PATH 中；钩子自身的第三方
    依赖由 uv 按 PEP 723 声明现场解析，不污染 Krita 的 Python 环境。

    本函数只做降级提示，不抛异常：导出与剪贴板复制已经完成，不能因为送达失败
    让用户以为整件事没成功。
    """
    hooks_dir = _resolve_hooks_dir()
    if not hooks_dir:
        _warn_open_workflow(
            f"未设置 {HOOK_DIR_ENV_VAR}，且无法定位默认钩子目录（APPDATA 缺失）。"
        )
        return
    if not image_path:
        _warn_open_workflow("当前文档尚未保存到磁盘，无法读取内嵌工作流。")
        return
    if not os.path.isfile(os.path.join(hooks_dir, "runner.py")):
        _warn_open_workflow(f"钩子目录下没有 runner.py：\n{hooks_dir}")
        return
    uv = shutil.which("uv")
    if not uv:
        _warn_open_workflow("找不到 uv，请把它加入 PATH。")
        return

    env = dict(os.environ)
    env["IMAGE_FUNNEL_IMAGE_PATHS"] = json.dumps([os.path.abspath(image_path)])
    try:
        result = subprocess.run(
            [uv, "run", "runner.py", "comfyui.open_workflow"],
            cwd=hooks_dir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # 不分配控制台窗口：否则 uv.exe 作为控制台程序会拿到一个新控制台，
            # Windows Terminal 按「附加到最近使用的窗口」把已有终端带到前台，
            # 盖住刚激活的 ComfyUI 窗口
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError as error:
        _warn_open_workflow(f"启动 uv 失败：{error}")
        return

    if result.returncode != 0:
        reason = _last_line(result.stderr) or _last_line(result.stdout)
        _warn_open_workflow(reason or f"uv 以退出码 {result.returncode} 结束。")


def _after_export(image_path):
    """
    导出收尾（在事件循环空闲后执行）：送达原图内嵌工作流并切到 ComfyUI 窗口。

    窗口激活由 image-funnel 的 open_workflow 钩子完成，本脚本不再枚举窗口。
    钩子内部会先送达工作流再激活窗口，因此即使激活失败，工作流也已经送达，
    用户手动切换后即可看到。
    """
    _open_embedded_workflow_or_warn(image_path)


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

    前提：文档结构为单个颜料层 + 一个透明度蒙版子节点，
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

    transparency_masks = [
        n for n in paint_layer.childNodes() if n.type() == "transparencymask"
    ]
    if not transparency_masks:
        raise RuntimeError(
            "颜料层的透明度蒙版缺失。导出结果依赖蒙版提供有效区域，"
            "没有它只会得到一张空蒙版，ComfyUI 会输出与输入完全一致的图。"
            "如果是直接在颜料层上涂抹而忘了新建透明度蒙版，"
            "请选中颜料层后「图层 > 新建 > 透明度蒙版」，再把涂抹内容放进蒙版。"
        )
    if len(transparency_masks) > 1:
        raise RuntimeError(
            f"颜料层下有 {len(transparency_masks)} 个透明度蒙版，本脚本只支持一个。"
        )
    transparency_mask = transparency_masks[0]

    # ---- 取颜料层原始像素（Krita 内部为 BGRA 字节序） ----
    ld = bytes(paint_layer.pixelData(0, 0, w, h))
    expected = w * h * 4
    if len(ld) != expected:
        raise RuntimeError(
            f"颜料层像素数据长度异常：{len(ld)}，期望 {expected}。"
        )

    # ---- 取透明蒙版 Alpha（1 字节/像素） ----
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

    # 原图路径用于读取内嵌工作流；文档未保存到磁盘时为空
    source_path = doc.fileName()
    doc_name = os.path.splitext(os.path.basename(source_path or "untitled"))[0]
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

    # 导出成功即视为本次工作已落盘，清掉文档的修改标记，避免退出时
    # 弹出「是否保存」确认。注意：这不会把改动写回原文件。
    doc.setModified(False)

    try:
        copy_file_to_clipboard(export_path)
    except Exception as e:
        QMessageBox.warning(
            None,
            "剪贴板",
            f"文件已导出到：\n{export_path}\n\n但复制到剪贴板失败：\n{e}",
        )
        return export_path

    # ---- 送达工作流并切到 ComfyUI ----
    # Ten Scripts 在 main() 返回后还会在 Krita 窗口上显示浮动通知，把 Krita
    # 重新提到前台，覆盖钩子做的窗口激活。因此把调用推迟到事件循环空闲后执行，
    # 确保它发生在 Krita 的收尾动作之后。
    QTimer.singleShot(
        ACTIVATION_DELAY_MS, lambda: _after_export(source_path)
    )
    return export_path


def main():
    """
    Ten Scripts 入口。

    Ten Scripts 通过 importlib 加载本文件后，会查找并调用名为 main 的可调用对象。
    """
    return export_and_copy()
