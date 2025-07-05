#!/usr/bin/env python3
"""
ComfyUI PNG文件重命名工具

该脚本根据ComfyUI生成的PNG文件中嵌入的提示词(prompt)元数据，重命名图像文件及其配套文件。
主要功能：
1. 从PNG元数据中提取提示词文本
2. 使用提示词的第一行作为新文件名的基础（排除包含指定关键词的行）
3. 自动处理配套文件（与主文件关联的元数据文件）
4. 生成包含文件修改日期和随机字符串的新文件名
5. 自动递增数字避免文件覆盖
6. 可选择为每个标题创建单独目录

特性：
- 支持多个文件路径作为输入
- 可选指定节点ID（按顺序尝试匹配）
- 可选排除包含特定关键词的行
- 文件名合法化处理（移除非法字符）
- 配套文件自动关联重命名
- 安全重命名（不覆盖已有文件）
- 可选择平面文件结构或目录结构
- 不考虑竞态，用户应保证运行时没有其他进程干扰

使用示例：
1. 基本使用：重命名单个文件
   python rename-comfyui-png.py image.png

2. 批量重命名多个文件：
   python rename-comfyui-png.py *.png

3. 指定节点ID和排除关键词：
   python rename-comfyui-png.py workflow.png -n 12,7,3 -e placeholder -e test

4. 区分大小写排除关键词：
   python rename-comfyui-png.py output.png -e "SAMPLE" -c

5. 使用目录结构（每个标题创建单独目录）：
   python rename-comfyui-png.py result.png --with-dir

参数说明：
  files           要处理的ComfyUI PNG文件路径（可多个）
  -n, --node-ids  指定优先使用的节点ID（多个节点按顺序尝试）
  -e, --exclude-keywords 排除包含这些关键词的行（可多次指定）
  -c, --case-sensitive  关键词区分大小写
  --with-dir 为每个标题创建单独的目录
"""


import os
import re
import json
import argparse
import hashlib
import logging
import datetime as dt
import random
from PIL import Image
from typing import (
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Iterator,
    Sequence,
    Iterable,
)
import glob

_LOGGER = logging.getLogger(__name__)


class PromptValueInputs(TypedDict):
    text: str
    clip: List[str]
    ckpt_name: str
    width: int
    height: int
    batch_size: int
    samples: List[str]
    vae: List[str]
    filename_prefix: str
    images: List[str]
    seed: int
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    denoise: float
    basic_pipe: List[str]
    latent_image: List[str]
    image: str
    conditioning_to: List[str]
    conditioning_from: List[str]


class PromptValue(TypedDict):
    inputs: PromptValueInputs
    class_type: str
    _meta: Dict[str, str]


Prompt = Dict[str, PromptValue]


def extract_prompt_from_png(file_path: str) -> Optional[Prompt]:
    """从PNG文件中提取ComfyUI元数据"""
    try:
        with Image.open(file_path) as img:
            if "prompt" in img.info:
                return json.loads(img.info["prompt"])
    except Exception as e:
        _LOGGER.error(f"Error reading {file_path}: {e}")
    return None


# 预编译正则表达式，用于匹配无效文件名字符
# reference https://github.com/parshap/node-sanitize-filename/blob/master/index.js
invalid_filename_char_pattern = re.compile(
    r'[/?<>\\:*|"\x00-\x1f\x80-\x9f]'  # 非法特殊字符
    r"|^\.+$"  # 全点号文件名
    r"|[. ]+$"  # 结尾的点号或空格
    r"|^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$",  # 保留名称
    flags=re.I,
)

MAX_FILENAME_BYTES = 255
FILENAME_TRUNCATE_SUFFIX = "...(%d more)"


def sanitize_filename(filename: str, revered_bytes: int = 64) -> str:
    # 替换无效字符为 U+FFFD (�)
    sanitized = invalid_filename_char_pattern.sub("\ufffd", filename)

    max_bytes = MAX_FILENAME_BYTES - revered_bytes
    max_chars = max_bytes
    while len(sanitized[:max_chars].encode("utf-8")) > max_bytes:
        max_chars -= 1
    # 如果长度超过限制则截断
    if len(sanitized) > max_chars:
        # 计算最大可能的截断后缀的长度，实际删除数量比这个少所以肯定更短
        # 后缀是常量，没包含多字节字符所以不会导致超过上限
        max_suffix = FILENAME_TRUNCATE_SUFFIX % (len(sanitized) - 1)
        max_suffix_length = len(max_suffix)

        # 计算保留字符数量
        keep_length = max_chars - max_suffix_length  # 为最长的后缀保留空间
        actual_remove_count = (
            len(sanitized) - keep_length
        )  # 一定小于 len(sanitized)-1, 所以实际后缀一定更短或相同长度

        # 生成最终带后缀的字符串
        truncated = sanitized[:keep_length]
        suffix = FILENAME_TRUNCATE_SUFFIX % actual_remove_count
        # ∵ keep_length + max_suffix_length == max_char
        # ∵ len(suffix) ≤ max_suffix_length
        # ∴ keep_length + len(suffix) ≤ max_char
        return truncated + suffix

    return sanitized


def title_from_prompt(
    prompt: Prompt,
    node_ids: Optional[List[str]] = None,
    exclude_keywords: Sequence[str] = (),
    case_sensitive: bool = False,
) -> Optional[Tuple[str, str]]:
    # 搜索所有包含text的节点
    # 没有指定节点ID时，按 ID 顺序，ID必定是数字，如果改了接口此脚本应根据具体更改做变更而不是提前猜会怎么改
    for node_id in node_ids or sorted(prompt.keys(), key=lambda id: int(id)):
        node = prompt.get(node_id)
        if node:
            text = node["inputs"].get("text")
            if text:
                return extract_title(text, exclude_keywords, case_sensitive), node_id

    return None


def extract_title(
    text: str,
    exclude_keywords: Sequence[str] = (),
    case_sensitive: bool = False,
) -> str:
    lines = text.splitlines()

    # 准备排除关键词
    exclude_set = set(
        exclude_keywords if case_sensitive else [k.lower() for k in exclude_keywords]
    )

    # 过滤行
    for line in lines:
        s = line.strip()
        if not s:
            continue

        # 检查是否包含排除关键词
        check_line = s if case_sensitive else s.lower()
        if any(keyword in check_line for keyword in exclude_set):
            continue

        s = s.removeprefix("//")  # 去掉注释符号，注释本身是可以用来当文件名的
        s = s.replace(r"\(", "(").replace(r"\)", ")")  # 去除提示词中的转义
        s = s.replace(" ", "_")  # 避免空格
        s = sanitize_filename(s).strip(" _,")
        if s:
            return s

    raise ValueError("所有行都被排除")


def find_companion_files(main_file: str) -> Iterator[tuple[str, str]]:
    """
    查找所有配套文件
    配套文件为相同目录下所有文件名符合`{包含扩展名的主文件名}.{任意后缀}`的文件，
    必须包含主文件的原始扩展名。例如主文件是`example.png`，
    则`example.png.xmp`是配套文件，而`example.png2`,`example.jpg`不是配套文件
    """
    main_basename = os.path.basename(main_file)
    directory = os.path.dirname(main_file) or "."

    # 简单前缀匹配：以原文件全名后跟一个点的文件
    prefix = main_basename + "."
    with os.scandir(directory) as it:
        for entry in it:
            if entry.is_file() and entry.name.startswith(prefix):
                yield (
                    os.path.join(directory, entry.name),
                    entry.name[len(main_basename) :],
                )


def generate_filename(
    title: str,
    directory: str,
    stat: os.stat_result,
    original_ext: str,
    with_dir: bool,
) -> str:
    # 文件名尽量幂等，方便在多个仓库之间合并，所以不使用数字序号

    try:
        min_time = min(stat.st_birthtime, stat.st_mtime)
    except:
        min_time = stat.st_mtime
    date_str = dt.datetime.fromtimestamp(min_time).strftime("%Y%m%d_%H%M%S")
    size_str = hex(stat.st_size)[2:]
    random_str = ""
    if with_dir:
        os.makedirs(os.path.join(directory, title), exist_ok=True)
    while True:
        name: str
        if with_dir:
            name = f"{title}/{date_str}_{size_str}{random_str}{original_ext}"
        else:
            name = f"{title}_{date_str}_{size_str}{random_str}{original_ext}"
        if not os.path.exists(os.path.join(directory, name)):
            return name
        random_str = "_" + random.randbytes(4).hex()


def rename_files(
    file_paths: Iterable[str],
    node_ids: Optional[List[str]] = None,
    exclude_keywords: Optional[List[str]] = None,
    case_sensitive: bool = False,
    with_dir: bool = False,
):
    """重命名主文件和配套文件"""
    exclude_keywords = exclude_keywords or []

    for file_path in file_paths:
        if not os.path.exists(file_path):
            _LOGGER.error(f"文件不存在: {file_path}")
            continue

        # 提取提示词
        prompt = extract_prompt_from_png(file_path)
        if not prompt:
            _LOGGER.warning(f"无法提取提示词: {file_path}")
            continue

        try:
            # 获取第一行文本
            result = title_from_prompt(
                prompt, node_ids, exclude_keywords, case_sensitive
            )
            if not result:
                _LOGGER.warning(f"未找到有效文本节点: {file_path}")
                continue

            title, _ = result
            if not title:
                _LOGGER.warning(f"提取到的文本为空: {file_path}")
                continue

            if not with_dir and os.path.normcase(
                os.path.basename(file_path)
            ).startswith(os.path.normcase(title)):
                _LOGGER.debug(f"跳过已经使用 prompt 命名的文件: {file_path}")
                continue

            # 准备重命名
            directory = os.path.dirname(file_path) or "."
            original_ext = os.path.splitext(file_path)[-1]

            # 生成新文件名
            stat = os.stat(file_path)
            new_basename = generate_filename(
                title, directory, stat, original_ext, with_dir
            )
            new_main_file = os.path.join(directory, new_basename)

            # 先查找并重命名配套文件，这样如果中途中断，只要再运行一次就能恢复成正常状态
            # 配套文件基于主文件名创建，但​​不影响主文件名生成​​
            # 所以下次无外部编辑的情况下再运行相当于从中断的地方继续，和直接成功没有区别(而先重命名主文件就会导致配套文件孤立了无法继续)
            for comp_file, suffix in find_companion_files(file_path):
                new_comp_file = new_main_file + suffix
                if not os.path.exists(new_comp_file):
                    os.rename(comp_file, new_comp_file)
                    _LOGGER.info(
                        f"重命名: {comp_file} -> {new_basename+suffix} (配套文件)"
                    )
                else:
                    _LOGGER.warning(f"配套文件已存在，跳过: {new_comp_file}")

            # 重命名主文件
            if not os.path.exists(new_main_file):
                os.rename(file_path, new_main_file)
                _LOGGER.info(f"重命名: {file_path} -> {new_basename} (主文件)")
            else:
                _LOGGER.warning(f"目标文件已存在，跳过: {new_main_file}")
                continue

        except Exception as e:
            _LOGGER.error(f"处理文件 {file_path} 时出错: {str(e)}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="根据ComfyUI PNG提示词重命名文件",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "files", nargs="+", help="要处理的ComfyUI PNG文件路径，支持通配符"
    )
    parser.add_argument(
        "-n", "--node-ids", help="指定要使用的节点ID（多个节点按顺序尝试，逗号分隔）"
    )
    parser.add_argument(
        "-e",
        "--exclude-keywords",
        action="append",
        help="要从文本中排除的关键词（可多次指定）",
    )
    parser.add_argument(
        "-c", "--case-sensitive", action="store_true", help="关键词区分大小写"
    )
    parser.add_argument(
        "--with-dir", action="store_true", help="为每个标题创建单独的目录"
    )

    args = parser.parse_args()

    # 处理参数
    node_ids = args.node_ids.split(",") if args.node_ids else None

    rename_files(
        file_paths=(j for i in args.files for j in (glob.glob(i) or (i,))),
        node_ids=node_ids,
        exclude_keywords=args.exclude_keywords,
        case_sensitive=args.case_sensitive,
        with_dir=args.with_dir,
    )


if __name__ == "__main__":
    main()
