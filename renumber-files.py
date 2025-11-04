#!/usr/bin/env python3
"""
renumber-files.py

文件名数字前缀重命名
将目录中所有数字前缀改为排序后序号乘以10
支持幂等操作，可安全中断和恢复
不支持并发执行
"""

import os
import re
import sys
import math
import logging
from pathlib import Path
from typing import Tuple, Optional, Iterator

_LOGGER = logging.getLogger(__name__)


class _Context:
    def __init__(self, directory: str = ".") -> None:
        self.directory: Path = Path(directory)
        self.temp_prefix: str = "RENAME_93b94d73b9ab_"
        self.prefix_length = self.determine_prefix_length()
        self.renamed_count = 0
        self.number_pattern = re.compile(r"^(\d+)_(.+)")

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
        return f"{number:0{self.prefix_length}d}_{suffix}"

    def parse_final_name(
        self,
        file_path: Path,
    ) -> Optional[Tuple[int, str]]:
        """提取文件信息：数字前缀和剩余部分"""
        filename = file_path.name
        match = re.match(r"^(\d+)_(.+)", filename)
        if match:
            return int(match.group(1)), match.group(2)
        _LOGGER.debug("parse_final_name: 忽略：%s", filename)
        return None

    def format_temp_name(
        self,
        number: int,
        version: int,
        suffix: str,
    ) -> str:
        """生成临时文件名"""
        return f"{self.temp_prefix}{number}_{version}_{suffix}"

    def parse_temp_name(
        self,
        file_path: Path,
    ) -> Optional[Tuple[int, int, str]]:
        """提取文件信息：数字前缀和剩余部分"""
        if not file_path.name.startswith(self.temp_prefix):
            return None
        filename = file_path.name
        match = re.match(r"^(\d+)_(\d+)_(.+)", filename[len(self.temp_prefix) :])
        if match:
            return int(match.group(1)), int(match.group(2)), match.group(3)
        _LOGGER.debug("parse_temp_name: 忽略：%s", filename)
        return None

    def determine_prefix_length(self) -> int:
        """确定前缀长度"""
        count = 0
        for file_path in self.all_files():
            if file_path.name.startswith(self.temp_prefix) or re.match(
                r"^(\d+)_(.+)", file_path.name
            ):
                count += 1

        if count == 0:
            return 1
        max_number = (count + 1) * 10
        return math.floor(math.log10(max_number)) + 1

    def final_files(self) -> Iterator[Tuple[int, str, Path]]:
        """获取所有符合命名模式的文件"""
        for file_path in self.all_files():
            info = self.parse_final_name(file_path)
            if info:
                yield info[0], info[1], file_path

    def temp_files(self) -> Iterator[Tuple[int, int, str, Path]]:
        """临时文件的迭代器"""
        for file_path in self.all_files():
            info = self.parse_temp_name(file_path)
            if info:
                yield info[0], info[1], info[2], file_path

    def first_pass(self) -> int:
        """第一遍：将所有需要重命名的文件重命名为临时文件，并返回起始索引"""

        # 计算起始索引
        next_index = 0
        start_index = -1
        for number, suffix, src in sorted(self.final_files()):
            _LOGGER.debug("first_pass: %s", src.name)
            index = next_index
            next_index += 1
            expected_number = (index + 1) * 10
            if start_index < 0:
                if number == expected_number:
                    continue
                else:
                    start_index = index

            ok = False
            version = 0
            while not ok:
                try:
                    dst = src.parent / self.format_temp_name(number, version, suffix)
                    if dst.exists():
                        version += 1
                        continue
                    src.rename(dst)
                    self.renamed_count += 1
                    ok = True
                    _LOGGER.info("临时: %s -> %s", src.name, dst.name)
                except FileExistsError:
                    version += 1

        if start_index < 0:
            return next_index
        return start_index

    def second_pass(self, start_index: int) -> None:
        """第二遍：将临时文件重命名为最终文件名"""

        # 处理所有临时文件
        next_index = start_index

        for _, _, suffix, src in sorted(self.temp_files()):
            _LOGGER.debug("second_pass: %s", src.name)
            index = next_index
            next_index += 1

            dst = src.parent / self.format_final_name((index + 1) * 10, suffix)
            # 冲突说明有并发修改，报错属于预期行为
            src.rename(dst)
            self.renamed_count += 1
            _LOGGER.info("最终: %s -> %s", src.name, dst.name)

    def rename_files(self) -> None:
        """幂等的重命名函数 - 无条件执行两遍操作"""
        _LOGGER.info("处理目录: %s", self.directory.absolute())
        _LOGGER.info("前缀长度: %s", self.prefix_length)

        self.second_pass(self.first_pass())
        _LOGGER.info("重命名完成！共处理 %s 个文件", self.renamed_count)


def main() -> None:
    directory = sys.argv[1] if len(sys.argv) > 1 else "."

    if not os.path.exists(directory):
        _LOGGER.error("错误: 目录 '%s' 不存在", directory)
        sys.exit(1)

    if not os.path.isdir(directory):
        _LOGGER.error("错误: '%s' 不是目录", directory)
        sys.exit(1)

    try:
        ctx = _Context(directory)
        ctx.rename_files()
    except KeyboardInterrupt:
        _LOGGER.info("操作被用户中断")
        sys.exit(0)
    except Exception:
        _LOGGER.exception("出错")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
