#!/usr/bin/env python3
"""
在指定目录中查找并删除重复文件，保留字典序最小的文件，并支持排除特定文件模式。

该脚本通过比较文件标识符来识别重复文件，使用流式处理避免加载所有文件内容到内存。
保留文件名按字典序最小的文件，删除其他重复文件，并将删除的文件名输出到stdout。

参数:
    directory (str): 要扫描的目录路径
    --head-size (int): 文件头部块大小（字节），默认为4096
    --tail-size (int): 文件尾部块大小（字节），默认为4096
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

import os
import sys
import argparse
import hashlib
import fnmatch
from typing import Dict, Tuple, Any, List
import logging

_LOGGER = logging.getLogger(__name__)


BUFFER_SIZE = 16 * 4096  # 64KB 缓冲区


def compute_file_key(file_path: str, head_size: int, tail_size: int) -> Tuple[int, Any]:
    """
    计算文件的标识符和大小

    返回值: (size, identifier)
    - 当两个区块大小都为0时，返回修改时间(mtime)
    - 当任一区块大小为负时，返回整个文件的哈希
    - 否则返回首尾块内容的哈希
    """
    try:
        size = os.path.getsize(file_path)

        # 当两个区块大小都为0时，使用修改时间
        if head_size == 0 and tail_size == 0:
            return size, os.path.getmtime(file_path)

        # 当任一区块大小为负或两者覆盖整个文件大小时，计算整个文件的哈希
        if head_size < 0 or tail_size < 0 or (head_size + tail_size) >= size:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        break
                    hasher.update(data)
            return size, hasher.hexdigest()

        # 计算首尾块哈希
        hasher = hashlib.sha256()

        # 读取头部块
        with open(file_path, "rb") as f:
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
                tail_start = max(0, size - tail_size)
                if tail_start > 0:
                    f.seek(tail_start)

                tail_read = 0
                to_read = min(tail_size, size)
                while tail_read < to_read:
                    chunk_size = min(BUFFER_SIZE, to_read - tail_read)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hasher.update(data)
                    tail_read += len(data)

        return size, hasher.hexdigest()

    except Exception as e:
        raise RuntimeError(f"处理文件 '{file_path}' 失败: {e}")


def should_exclude_file(filename: str, exclude_patterns: List[str]) -> bool:
    """检查文件名是否匹配任一排除模式"""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def confirm_deletion(file_path: str) -> bool:
    """确认文件删除操作"""
    try:
        response = (
            input(f"删除文件 '{os.path.basename(file_path)}'? [y/N] ").strip().lower()
        )
        return response == "y"
    except KeyboardInterrupt:
        _LOGGER.info("操作已取消")
        sys.exit(1)


def delete_file(file_path: str, is_dry_run: bool, is_yes: bool) -> None:
    """删除文件，处理dry-run和确认逻辑"""
    if is_dry_run:
        print(file_path)
        return

    if not is_yes:
        if not confirm_deletion(file_path):
            _LOGGER.info(f"跳过: {file_path}")
            return

    try:
        os.remove(file_path)
        print(file_path)
    except Exception as e:
        raise RuntimeError(f"删除文件 '{file_path}' 失败: {e}")


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
    # 存储保留文件的信息: {(size, identifier): retained_file}
    retain_files: Dict[Tuple[int, Any], str] = {}

    try:
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

                try:
                    key = compute_file_key(file_path, head_size, tail_size)
                except Exception as e:
                    _LOGGER.error("错误: %s", e)
                    sys.exit(1)

                # 检查是否已有相同标识符的文件
                if key in retain_files:
                    retained_file = retain_files[key]

                    # 确定哪个文件应该保留（字典序最小的）
                    if file_path < retained_file:
                        # 当前文件更小，删除原来保留的文件
                        try:
                            delete_file(retained_file, is_dry_run, is_yes)
                        except Exception as e:
                            _LOGGER.error("错误: %s", e)
                            sys.exit(1)

                        # 更新保留文件为当前文件
                        retain_files[key] = file_path
                    else:
                        # 删除当前文件（保留原来的文件）
                        try:
                            delete_file(file_path, is_dry_run, is_yes)
                        except Exception as e:
                            _LOGGER.error("错误: %s", e)
                            sys.exit(1)
                else:
                    # 首次遇到该标识符，保留当前文件
                    retain_files[key] = file_path

    except Exception as e:
        _LOGGER.error("扫描目录错误: %s", e)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="在目录中查找并删除重复文件")
    parser.add_argument("directory", help="要扫描的目录路径")
    parser.add_argument(
        "--head-size",
        type=int,
        default=4096,
        help="头部块大小字节数（负数表示整个文件，0表示使用修改时间，默认: 4096)",
    )
    parser.add_argument(
        "--tail-size",
        type=int,
        default=4096,
        help="尾部块大小字节数（负数表示整个文件，0表示使用修改时间，默认: 4096)",
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
