#!/usr/bin/env python3
"""
在指定目录中查找并删除重复文件，保留字典序最小的文件，并支持排除特定文件模式。

该脚本通过比较文件指纹和完整内容识别重复文件，使用流式处理避免加载所有文件内容到内存。
保留文件名按字典序最小的文件，删除其他重复文件，并将删除的文件名输出到stdout。

功能特点:
1. 高效识别重复
2. 支持文件排除模式（支持多个--exclude参数）
3. 流式处理避免大文件内存占用
4. 保留字典序最小的文件名
5. 支持模拟运行(--dry-run)模式
6. 使用scandir高效目录扫描

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

    def __init__(self, /, is_dry_run: bool, is_yes: bool) -> None:
        self.is_dry_run = is_dry_run
        self.is_yes = is_yes
        self.files = list[_File]()
        self.fingerprint_size = (64 << 10, 64 << 10)
        # 优化：使用大小作为分组键，避免指纹计算开销
        # 通常大小就足够唯一，大部分情况应该是一个元素的列表，迭代列表比计算所有文件的指纹开销小很多
        self.index_by_size = defaultdict[int, List[int]](lambda: [])

        self.new_hasher = lambda: hashlib.md5()
        try:
            import xxhash

            self.new_hasher = lambda: xxhash.xxh64()
        except ImportError:
            _LOGGER.info("xxhash 不可用，使用回退算法")

    def add_file(self, f: _File):
        index = len(self.files)
        self.files.append(f)
        self.index_by_size[f.size()].append(index)

    def find_duplicate_index(self, f: _File) -> int:
        for index in self.index_by_size[f.size()]:
            candidate = self.files[index]
            if f is candidate:
                # 忽略自身
                continue
            if candidate.is_duplicate_of(f):
                return index
        return -1

    def deduplicate(self, entry: os.DirEntry[str]):
        f = _File(self, entry)
        duplicated_index = self.find_duplicate_index(f)
        if duplicated_index < 0:
            self.add_file(f)
        else:
            existing = self.files[duplicated_index]
            # 确定哪个文件应该删除（保留字典序最小的）
            duplicated = f
            if f.name() < existing.name():
                # 当前文件更小，替换原来保留的文件
                duplicated = existing
                self.files[duplicated_index] = f
            _LOGGER.info("重复文件: \n\t%s\n\t%s", *sorted((f.name(), existing.name())))
            delete_file(duplicated.path(), self.is_dry_run, self.is_yes)


class _File:

    def __init__(self, ctx: _Context, entry: os.DirEntry[str]) -> None:
        self.ctx = ctx
        self.entry = entry
        self._cached_stat: Optional[os.stat_result] = None
        self._cached_fingerprint: Optional[Any] = None

    def stat(self):
        if not self._cached_stat:
            self._cached_stat = self.entry.stat()
        return self._cached_stat

    def fingerprint(self):
        if not self._cached_fingerprint:
            self._cached_fingerprint = self._calculate_fingerprint()
        return self._cached_fingerprint

    def size(self):
        return self.stat().st_size

    def path(self):
        return self.entry.path

    def name(self):
        return self.entry.name

    def is_duplicate_of(self, other: _File) -> bool:
        if self.size() == 0 and other.size() == 0:
            # 优化：两个空文件肯定相同
            return True
    
        return (
            self.size() == other.size()
            and self.fingerprint() == other.fingerprint()
            and self.has_same_content(other)
        )

    def has_same_content(self, other: _File) -> bool:
        with open(self.entry.path, "rb") as file1, open(
            other.entry.path, "rb"
        ) as file2:
            while True:
                # 逐块读取文件内容
                chunk1 = file1.read(BUFFER_SIZE)
                chunk2 = file2.read(BUFFER_SIZE)

                # 如果读取到的内容不同，立即返回False
                if chunk1 != chunk2:
                    return False

                # 如果都读取到空字节（文件结束），则比较完成
                if not chunk1:
                    return True

    def _calculate_fingerprint(self):
        head_size, tail_size = self.ctx.fingerprint_size

        # 优化：当任一区块大小为负或两者覆盖整个文件大小时，计算整个文件的哈希
        if head_size < 0 or tail_size < 0 or (head_size + tail_size) >= self.size():
            hasher = self.ctx.new_hasher()
            with open(self.entry.path, "rb") as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()

        # 计算首尾块哈希
        hasher = self.ctx.new_hasher()

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
    ctx = _Context(is_dry_run=is_dry_run, is_yes=is_yes)

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

            ctx.deduplicate(entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="在目录中查找并删除重复文件")
    parser.add_argument("directory", help="要扫描的目录路径")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细输出日志",
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

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        _LOGGER.error("'%s' 不是有效目录", args.directory)
        sys.exit(1)

    # 处理目录
    process_directory(
        args.directory,
        args.exclude,
        args.dry_run,
        args.yes,
    )


if __name__ == "__main__":
    main()
