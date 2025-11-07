#!/bin/sh

grep -q '^## TUNA' /etc/pacman.d/mirrorlist.mingw32 || \
    sed '/^## Primary$/a## TUNA\nServer = https://mirrors.tuna.tsinghua.edu.cn/msys2/mingw/i686' \
    -i  /etc/pacman.d/mirrorlist.mingw32

grep -q '^## TUNA' /etc/pacman.d/mirrorlist.mingw64 || \
    sed '/^## Primary$/a## TUNA\nServer = https://mirrors.tuna.tsinghua.edu.cn/msys2/mingw/x86_64' \
    -i  /etc/pacman.d/mirrorlist.mingw64

grep -q '^## TUNA' /etc/pacman.d/mirrorlist.msys || \
    sed '/^## Primary$/a## TUNA\nServer = https://mirrors.tuna.tsinghua.edu.cn/msys2/msys/$arch' \
    -i  /etc/pacman.d/mirrorlist.msys

pacman -Sy
