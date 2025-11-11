#!/usr/bin/env python3
"""
renumber-files.py

文件名数字前缀重命名
将目录中所有数字前缀改为排序后序号，支持小数前缀。
支持幂等操作，可安全中断和恢复
不支持并发执行
"""

import os
import re
import sys
import math
import logging
from pathlib import Path
from collections import Counter
from typing import Tuple, Optional, Iterator

_LOGGER = logging.getLogger(__name__)


class _Context:
    def __init__(self, directory: str = ".") -> None:
        self.directory: Path = Path(directory)
        self.temp_prefix: str = "RENAME_93b94d73b9ab-"
        self.prefix_length = 1
        self.delimiter = "-"
        self.final_file_pattern = re.compile(
            r"^((?:\d*\.)?\d+)([-_ ]*)(.*)$",
        )
        self.prepare()

    def prepare(self):
        count = 0
        delimiter_counter = Counter[str]()
        for file_path in self.all_files():
            if file_path.name.startswith(self.temp_prefix):
                count += 1
            else:
                match = self.final_file_pattern.match(file_path.name)
                if match:
                    count += 1
                    delimiter = match.group(2)
                    delimiter_counter[delimiter] += 1
        for i, _ in delimiter_counter.most_common(1):
            self.delimiter = i
        if count > 0: # 避免 math.log10(0)
            self.prefix_length = 1 + math.floor(math.log10(count))

    def all_files(self) -> Iterator[Path]:
        """获取目录中所有文件"""
        for i in self.directory.iterdir():
            if i.is_file():
                yield i

    def format_final_name(
        self,
        number: int,
        suffix: str,
    ) -> str:
        """生成最终文件名"""
        return f"{number:0{self.prefix_length}d}{self.delimiter}{suffix}"

    def parse_final_name(
        self,
        file_path: Path,
    ) -> Optional[Tuple[float, str]]:
        """提取文件信息：数字前缀和剩余部分"""
        filename = file_path.name
        match = self.final_file_pattern.match(filename)
        if match:
            return float(match.group(1)), match.group(3)
        _LOGGER.debug("parse_final_name: 忽略：%s", filename)
        return None

    def format_temp_name(
        self,
        number: float,
        version: int,
        suffix: str,
    ) -> str:
        """生成临时文件名"""
        return f"{self.temp_prefix}{number}-{version}-{suffix}"

    def parse_temp_name(
        self,
        file_path: Path,
    ) -> Optional[Tuple[float, int, str]]:
        """提取文件信息：数字前缀和剩余部分"""
        if not file_path.name.startswith(self.temp_prefix):
            return None
        filename = file_path.name
        match = re.match(
            r"^((?:\d*\.)?\d+)-(\d+)-(.+)", filename[len(self.temp_prefix) :]
        )
        if match:
            return float(match.group(1)), int(match.group(2)), match.group(3)
        _LOGGER.debug("parse_temp_name: 忽略：%s", filename)
        return None

    def final_files(self) -> Iterator[Tuple[float, str, Path]]:
        """获取所有符合命名模式的文件"""
        for file_path in self.all_files():
            info = self.parse_final_name(file_path)
            if info:
                yield info[0], info[1], file_path

    def temp_files(self) -> Iterator[Tuple[float, int, str, Path]]:
        """临时文件的迭代器"""
        for file_path in self.all_files():
            info = self.parse_temp_name(file_path)
            if info:
                yield info[0], info[1], info[2], file_path


def renumber_files(dir: str):
    """幂等的重命名函数 - 无条件执行两遍操作"""
    ctx = _Context(dir)
    _LOGGER.debug("处理目录: %s", ctx.directory.absolute())
    _LOGGER.debug("前缀长度: %s", ctx.prefix_length)

    # 第一遍，将所有需重命名的文件放到临时命名空间下，以支持中断
    next_index = 0
    start_index = -1
    for number, suffix, src in sorted(ctx.final_files()):
        _LOGGER.debug("first_pass: %s", src.name)
        index = next_index
        next_index += 1
        expected_number = index + 1
        if start_index < 0:
            if number == expected_number and src.name == ctx.format_final_name(
                expected_number, suffix
            ):
                continue
            else:
                # 之后的所有文件都需要重命名
                start_index = index

        version = 0
        while True:  # 文件数量有限，不可能无限循环
            try:
                dst = src.parent / ctx.format_temp_name(number, version, suffix)
                if dst.exists():
                    version += 1
                    continue
                src.rename(dst)
                _LOGGER.debug("重命名为临时文件: %s -> %s", src.name, dst.name)
                break
            except FileExistsError:
                version += 1

    # 第二遍：将所有临时文件重命名
    # 因为总是从小到大进行重命名，残留的临时文件肯定是在最终文件后面
    next_index = next_index if start_index < 0 else start_index
    for _, _, suffix, src in sorted(ctx.temp_files()):
        _LOGGER.debug("second_pass: %s", src.name)
        index = next_index
        next_index += 1

        dst = src.parent / ctx.format_final_name(index + 1, suffix)
        # 不应处理冲突，因为非临时文件只可能是：
        # a. 没有数字前缀
        # b. 数字更小
        # c. 并发创建，而脚本不支持并发
        src.rename(dst)
        _LOGGER.info("%s -> %s", src.name, dst.name)


def main() -> None:
    directory = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.exists(directory):
        _LOGGER.error("错误: 目录 '%s' 不存在", directory)
        sys.exit(1)

    if not os.path.isdir(directory):
        _LOGGER.error("错误: '%s' 不是目录", directory)
        sys.exit(1)
    renumber_files(directory)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
