from ctypes import windll, pointer, sizeof
from typing import Tuple
import win32con
import win32gui
import win32api


def click(h_wnd: int, pos: Tuple[int, int]) -> None:
    x, y = pos
    l_param = win32api.MAKELONG(x, y)
    win32gui.PostMessage(h_wnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
    win32gui.PostMessage(h_wnd, win32con.WM_LBUTTONUP, None, l_param)


if __name__ == "__main__":
    h_wnd = 0x00000000
    for x in range(100, 300, 50):
        for y in range(100, 300, 50):
            click(h_wnd, (x, y))
