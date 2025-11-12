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
from typing import Tuple, Optional, Iterator, NamedTuple
import argparse

_LOGGER = logging.getLogger(__name__)


class _FinalFileInfo(NamedTuple):
    # 注意：字段顺序影响排序
    number: float
    suffix: str

    name: str
    delimiter: str


class _TempFileInfo(NamedTuple):
    # 注意：字段顺序影响排序
    number: float
    version: int
    suffix: str

    name: str
    raw_name: str


class _Context:
    def __init__(self, directory: str = ".") -> None:
        self.directory: Path = Path(directory)
        self.temp_prefix: str = (
            "RENAME_2ae509c0afcf_"  # 使用固定前缀以支持中断后恢复。不可标记为临时或隐藏，避免用户误认为文件丢失
        )
        self.prefix_length = 1
        self.delimiter = "-"
        self.final_file_pattern = re.compile(
            r"^((?:\d*\.)?\d+)([-_ ]*)(.*)$",
        )
        self.max_raw_name_length = 0
        self.prepare()

    def prepare(self):
        count = 0
        delimiter_counter = Counter[str]()
        for file_path in self.all_files():
            info = self.parse_temp_name(file_path.name)
            if info:
                self.max_raw_name_length = max(
                    self.max_raw_name_length,
                    len(info.raw_name),
                )
                continue

            info = self.parse_final_name(file_path.name)
            if info:
                self.max_raw_name_length = max(
                    self.max_raw_name_length,
                    len(info.name),
                )
                count += 1
                delimiter_counter[info.delimiter] += 1
        for i, _ in delimiter_counter.most_common(1):
            self.delimiter = i
        if count > 0:  # 避免 math.log10(0)
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
        name: str,
    ) -> Optional[_FinalFileInfo]:
        """提取文件信息：数字前缀和剩余部分"""
        match = self.final_file_pattern.match(name)
        if match:
            return _FinalFileInfo(
                name=name,
                number=float(match.group(1)),
                delimiter=match.group(2),
                suffix=match.group(3),
            )
        _LOGGER.debug("parse_final_name: 忽略：%s", name)
        return None

    def format_temp_name(
        self,
        version: int,
        raw_name: str,
    ) -> str:
        """生成临时文件名"""
        return f"{self.temp_prefix}{version}-{raw_name}"

    def parse_temp_name(
        self,
        name: str,
    ) -> Optional[_TempFileInfo]:
        if not name.startswith(self.temp_prefix):
            return None
        # 既然有前缀，就必须符合格式。
        # 不匹配视为代码问题，应立即崩溃防止错误扩大。
        info = re.match(r"^(\d+)-(.*)", name[len(self.temp_prefix) :])
        if not info:
            raise ValueError("无法识别临时文件 %s", name)
        version = int(info.group(1))
        raw_name = info.group(2)
        info = self.parse_final_name(raw_name)
        if not info:
            raise ValueError("无法识别临时文件 %s", name)
        return _TempFileInfo(
            name=name,
            raw_name=raw_name,
            version=version,
            number=info.number,
            suffix=info.suffix,
        )

    def final_files(self) -> Iterator[Tuple[_FinalFileInfo, Path]]:
        """获取所有符合命名模式的文件"""
        for file_path in self.all_files():
            info = self.parse_final_name(file_path.name)
            if info:
                yield info, file_path

    def temp_files(self) -> Iterator[Tuple[_TempFileInfo, Path]]:
        """临时文件的迭代器"""
        for file_path in self.all_files():
            info = self.parse_temp_name(file_path.name)
            if info:
                yield info, file_path


class RenumberItem(NamedTuple):
    src: Path
    dst: Path
    old_number: float
    new_number: int
    suffix: str

    ctx: _Context


def renumber_files(dir: str) -> Iterator[RenumberItem]:
    """
    幂等的重命名函数 - 无条件执行两遍操作
    返回（原始文件路径, 新文件路径，原始数字前缀，新数字前缀，）。
    """
    ctx = _Context(dir)
    _LOGGER.debug("处理目录: %s", ctx.directory.absolute())
    _LOGGER.debug("前缀长度: %s", ctx.prefix_length)

    # 第一遍，将所有需重命名的文件放到临时命名空间下，以支持中断
    next_index = 0
    start_index = -1
    for info, src in sorted(ctx.final_files()):
        _LOGGER.debug("first_pass: %s", src.name)
        index = next_index
        next_index += 1
        expected_number = index + 1
        if start_index < 0:
            if info.number == expected_number and src.name == ctx.format_final_name(
                expected_number, info.suffix
            ):
                yield RenumberItem(
                    src,
                    src,
                    info.number,
                    expected_number,
                    ctx.delimiter,
                    ctx,
                )
                continue
            else:
                # 之后的所有文件都需要重命名
                start_index = index

        version = 0
        while True:  # 文件数量有限，不可能无限循环
            try:
                dst = src.parent / ctx.format_temp_name(version, src.name)
                if dst.exists():
                    version += 1
                    continue
                src.rename(dst)
                _LOGGER.debug("重命名为临时文件: %s => %s", src.name, dst.name)
                break
            except FileExistsError:
                version += 1

    # 第二遍：将所有临时文件重命名
    # 因为总是从小到大进行重命名，残留的临时文件肯定是在最终文件后面
    if start_index >= 0:
        # 从已经移走的索引开始重新分配序号
        next_index = start_index
    for info, src in sorted(ctx.temp_files()):
        _LOGGER.debug("second_pass: %s", src.name)
        index = next_index
        next_index += 1

        dst = src.parent / ctx.format_final_name(index + 1, info.suffix)
        # 序号唯一，不可能有冲突，因为非临时文件只可能是：
        # a. 没有数字前缀
        # b. 数字更小
        # c. 并发创建，而脚本不支持并发
        src.rename(dst)
        _LOGGER.debug("%s => %s", src.name, dst.name)
        yield RenumberItem(
            src.parent / info.raw_name,
            dst,
            info.number,
            index + 1,
            info.suffix,
            ctx,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", default=".", help="输入目录")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细日志输出",
    )

    args = parser.parse_args()

    log_level: int = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if not os.path.exists(args.directory):
        _LOGGER.error("错误: 目录 '%s' 不存在", args.directory)
        sys.exit(1)

    if not os.path.isdir(args.directory):
        _LOGGER.error("错误: '%s' 不是目录", args.directory)
        sys.exit(1)
    for i in renumber_files(args.directory):
        if i.src.name != i.dst.name:
            print(
                f"{i.src.name}\t{' ' * (i.ctx.max_raw_name_length - len(i.src.name))}=>\t{i.dst.name}"
            )


if __name__ == "__main__":
    main()
