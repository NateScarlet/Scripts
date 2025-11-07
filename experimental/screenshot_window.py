import argparse
from ctypes import windll

import cv2
import numpy as np
import win32con
import win32gui
import win32ui


# https://stackoverflow.com/a/62293979
def screenshot_bitblt(h_wnd):
    window_dc = win32gui.GetWindowDC(h_wnd)
    handle_dc = win32ui.CreateDCFromHandle(window_dc)
    left, top, width, height = win32gui.GetClientRect(h_wnd)
    compatible_dc = handle_dc.CreateCompatibleDC()
    try:
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(handle_dc, width, height)
        compatible_dc.SelectObject(bitmap)
        compatible_dc.BitBlt(
            (left, top), (width, height), handle_dc, (0, 0), win32con.SRCCOPY
        )
        return np.frombuffer(bitmap.GetBitmapBits(True), dtype=np.uint8).reshape(
            (height, width, 4)
        )

    finally:
        handle_dc.DeleteDC()
        compatible_dc.DeleteDC()
        win32gui.ReleaseDC(h_wnd, window_dc)


PW_CLIENT_ONLY = 1 << 0
import sys

# https://docs.microsoft.com/en-us/windows/win32/winprog/using-the-windows-headers
_WIN32_WINNT_WINBLUE = 0x0603


def _win_ver():
    v = sys.getwindowsversion()
    return v.major << 8 | v.minor


_WIN32_WINNT = _win_ver()

# https://stackoverflow.com/a/40042587
PW_RENDERFULLCONTENT = 1 << 1
if _WIN32_WINNT < _WIN32_WINNT_WINBLUE:
    PW_RENDERFULLCONTENT = 0

# https://stackoverflow.com/a/24352388
def screenshot_print_window(h_wnd):
    window_dc = win32gui.GetWindowDC(h_wnd)
    handle_dc = win32ui.CreateDCFromHandle(window_dc)
    _, _, width, height = win32gui.GetClientRect(h_wnd)
    compatible_dc = handle_dc.CreateCompatibleDC()
    try:
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(handle_dc, width, height)

        compatible_dc.SelectObject(bitmap)
        result = windll.user32.PrintWindow(
            h_wnd,
            compatible_dc.GetSafeHdc(),
            PW_CLIENT_ONLY | PW_RENDERFULLCONTENT,
        )
        if result != 1:
            raise RuntimeError("Print window failed: %s" % result)
        return np.frombuffer(bitmap.GetBitmapBits(True), dtype=np.uint8).reshape(
            (height, width, 4)
        )
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        handle_dc.DeleteDC()
        compatible_dc.DeleteDC()
        win32gui.ReleaseDC(h_wnd, window_dc)

# TODO: investigate windows graphics capture
# https://docs.microsoft.com/en-us/uwp/api/windows.graphics.capture
# https://github.com/obsproject/obs-studio/blob/master/libobs-winrt/winrt-capture.cpp#L284

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("h_wnd", type=lambda x: int(x, 0))
    args = parser.parse_args()
    h_wnd = args.h_wnd

    bitblt_result = screenshot_bitblt(h_wnd)
    print_window_result = screenshot_print_window(h_wnd)
    try:
        cv2.imshow("bitblt", bitblt_result)
        cv2.imshow("print_window", print_window_result)
        cv2.waitKey()
    finally:
        cv2.destroyAllWindows()
