from typing import Tuple
import win32con
import win32gui
import win32api
import argparse


def click(h_wnd: int, pos: Tuple[int, int]) -> None:
    x, y = pos
    l_param = win32api.MAKELONG(x, y)
    win32gui.PostMessage(h_wnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, l_param)
    win32gui.PostMessage(h_wnd, win32con.WM_LBUTTONUP, None, l_param)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("h_wnd", type=lambda x: int(x, 0))
    args = parser.parse_args()
    h_wnd = args.h_wnd

    for x in range(100, 300, 50):
        for y in range(100, 300, 50):
            click(h_wnd, (x, y))
