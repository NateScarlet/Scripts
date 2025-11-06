#!/usr/bin/env python3
"""
在指定目录中查找并删除重复文件，保留字典序最小的文件，并支持排除特定文件模式。

该脚本通过比较文件标识符来识别重复文件，使用流式处理避免加载所有文件内容到内存。
保留文件名按字典序最小的文件，删除其他重复文件，并将删除的文件名输出到stdout。

参数:
    directory (str): 要扫描的目录路径
    --head-size (int): 文件头部块大小（字节），默认为16384
    --tail-size (int): 文件尾部块大小（字节），默认为16384
    --exclude (str): 要排除的文件模式（可多次使用）
    --dry-run: 仅列出要删除的文件而不实际删除
    -y/--yes: 跳过删除确认步骤，直接删除

功能特点:
1. 使用文件大小和标识符识别重复
2. 支持文件排除模式（支持多个--exclude参数）
3. head-size或tail-size任一为负数时检查整个文件
4. 两个区块大小都设为0时使用修改时间作为标识
5. 流式处理避免大文件内存占用
6. 保留字典序最小的文件名
7. 支持模拟运行(--dry-run)模式
8. 错误处理与详细错误输出
9. 使用scandir高效目录扫描
10. 实时处理避免收集所有文件

使用示例:
    # 排除所有.log和.tmp文件
    python3 remove-duplicated-file.py /path/to/files --exclude "*.log" --exclude "*.tmp"

    # 排除以temp开头的文件
    python3 remove-duplicated-file.py /path/to/files --exclude "temp*"

    # 模拟运行（仅列出要删除的文件）
    python3 remove-duplicated-file.py /path/to/files --dry-run

    # 直接删除无需确认
    python3 remove-duplicated-file.py /path/to/files -y

注意事项:
1. 只处理常规文件（跳过目录/符号链接）
2. 不扫描子目录
3. 删除操作前务必使用--dry-run确认
4. 文件比较区分大小写
5. 所有错误消息输出到stderr
6. 排除模式支持fnmatch语法
"""
from __future__ import annotations
import os
import sys
import argparse
import hashlib
import fnmatch
from typing import List, Optional, Any
import logging
from collections import defaultdict


_LOGGER = logging.getLogger(__name__)

BUFFER_SIZE = 64 << 10  # 64KB 缓冲区


class _Context:

    def __init__(self, head_size: int, tail_size: int) -> None:
        self.head_size = head_size
        self.tail_size = tail_size
        self.files = list[_File]()
        self.index_by_size = defaultdict[int, List[int]](lambda: [])
        # 优化：避免用哈希作为分组键，因为文件大小唯一的概率很高，哈希计算开销较高

    def new_file(self, entry: os.DirEntry[str]) -> _File:
        return _File(self, entry)

    def add_file(self, f: _File):
        index = len(self.files)
        self.files.append(f)
        self.index_by_size[f.size()].append(index)

    def find_duplicated_index(self, f: _File) -> int:
        for index in self.index_by_size[f.size()]:
            candidate = self.files[index]
            if f is candidate:
                # 忽略自身
                continue
            if candidate.is_duplicated_with(f):
                return index
        return -1


class _File:

    def __init__(self, ctx: _Context, entry: os.DirEntry[str]) -> None:
        self.ctx = ctx
        self.entry = entry
        self._cached_stat: Optional[os.stat_result] = None
        self._cached_key: Optional[Any] = None

    def stat(self):
        if not self._cached_stat:
            self._cached_stat = self.entry.stat()
        return self._cached_stat

    def key(self):
        if not self._cached_key:
            self._cached_key = self._compute_key()
        return self._cached_key

    def size(self):
        return self.stat().st_size

    def path(self):
        return self.entry.path

    def is_duplicated_with(self, other: _File) -> bool:
        return self.size() == other.size() and self.key() == other.key()

    def _compute_key(self):
        head_size = self.ctx.head_size
        tail_size = self.ctx.tail_size
        if head_size == 0 and tail_size == 0:
            # 当两个区块大小都为0，不使用内容key
            return self.stat().st_mtime

        # 当任一区块大小为负或两者覆盖整个文件大小时，计算整个文件的哈希
        if head_size < 0 or tail_size < 0 or (head_size + tail_size) >= self.size():
            hasher = hashlib.sha256()
            with open(self.entry.path, "rb") as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()

        # 计算首尾块哈希
        hasher = hashlib.sha256()

        # 读取头部块
        with open(self.entry.path, "rb") as f:
            if head_size > 0:
                head_read = 0
                while head_read < head_size:
                    chunk_size = min(BUFFER_SIZE, head_size - head_read)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hasher.update(data)
                    head_read += len(data)

            # 读取尾部块
            if tail_size > 0:
                tail_start = max(0, self.size() - tail_size)
                if tail_start > 0:
                    f.seek(tail_start)

                tail_read = 0
                to_read = min(tail_size, self.size())
                while tail_read < to_read:
                    chunk_size = min(BUFFER_SIZE, to_read - tail_read)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hasher.update(data)
                    tail_read += len(data)

        return hasher.hexdigest()


def should_exclude_file(filename: str, exclude_patterns: List[str]) -> bool:
    """检查文件名是否匹配任一排除模式"""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def confirm_deletion(file_path: str) -> bool:
    """确认文件删除操作"""
    response = (
        input(f"删除文件 '{os.path.basename(file_path)}'? [y/N] ").strip().lower()
    )
    return response == "y"


def delete_file(file_path: str, is_dry_run: bool, is_yes: bool) -> None:
    """删除文件，处理dry-run和确认逻辑"""
    if is_dry_run:
        print(file_path)
        return

    if not is_yes:
        if not confirm_deletion(file_path):
            _LOGGER.info(f"跳过: {file_path}")
            return

    os.remove(file_path)
    print(file_path)


def process_directory(
    directory: str,
    head_size: int,
    tail_size: int,
    exclude_patterns: List[str],
    is_dry_run: bool,
    is_yes: bool,
) -> None:
    """
    流式处理目录，查找并处理重复文件，支持排除特定模式的文件

    使用字典保存每组文件的保留文件:
        key: (文件大小, 标识符)
        value: 要保留的文件路径（字典序最小的）
    """
    ctx = _Context(head_size, tail_size)

    # 使用scandir流式处理目录
    with os.scandir(directory) as entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False):
                continue

            file_path = entry.path
            file_name = entry.name

            # 检查是否应该排除该文件
            if should_exclude_file(file_name, exclude_patterns):
                _LOGGER.debug("排除文件: %s", file_path)
                continue

            f = ctx.new_file(entry)

            # 检查是否已有重复文件
            duplicated_index = ctx.find_duplicated_index(f)
            if duplicated_index < 0:
                ctx.add_file(f)
            else:
                existing = ctx.files[duplicated_index]
                # 确定哪个文件应该删除（保留字典序最小的）
                duplicated = f
                if f.path() < existing.path():
                    # 当前文件更小，替换原来保留的文件
                    duplicated = existing
                    ctx.files[duplicated_index] = f
                delete_file(duplicated.path(), is_dry_run, is_yes)


def main() -> None:
    parser = argparse.ArgumentParser(description="在目录中查找并删除重复文件")
    parser.add_argument("directory", help="要扫描的目录路径")
    parser.add_argument(
        "--head-size",
        type=int,
        default=16384,
        help="头部块大小字节数（负数表示整个文件，0表示使用修改时间，默认: 16384)",
    )
    parser.add_argument(
        "--tail-size",
        type=int,
        default=16384,
        help="尾部块大小字节数（负数表示整个文件，0表示使用修改时间，默认: 16384)",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="append",
        default=[],
        help="排除的文件名模式（支持通配符，可多次使用）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅列出不实际删除",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="无需确认直接删除")
    args = parser.parse_args()

    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        _LOGGER.error("'%s' 不是有效目录", args.directory)
        sys.exit(1)

    # 处理目录
    process_directory(
        args.directory,
        args.head_size,
        args.tail_size,
        args.exclude,
        args.dry_run,
        args.yes,
    )


if __name__ == "__main__":
    main()
