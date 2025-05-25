import os
import argparse
import json
from PIL import Image
from typing import Dict, Optional

import logging

_LOGGER = logging.getLogger(__name__)


def extract_comfyui_metadata_from_png(file_path: str) -> Optional[Dict]:
    """从PNG文件中提取ComfyUI元数据"""
    try:
        with Image.open(file_path) as img:
            # show image info
            # ComfyUI 将元数据存储在 "prompt" 文本块中
            if "prompt" in img.info:
                return json.loads(img.info["prompt"])
            elif "workflow" in img.info:
                return json.loads(img.info["workflow"])
        return None
    except Exception as e:
        _LOGGER.error(f"Error reading {file_path}: {e}")
        return None


def find_pngs_with_prompt(
    keyword: str,
    directory: str = ".",
) -> None:
    """在指定目录查找PNG文件中prompt包含关键字的图片"""
    _LOGGER.info(f"在目录 '{directory}' 中搜索 prompt 包含 '{keyword}' 的PNG图片...")
    found_count = 0

    for filename in os.listdir(directory):
        if filename.lower().endswith(".png"):
            _LOGGER.debug(f"正在读取文件: {filename}")
            file_path = os.path.join(directory, filename)
            metadata = extract_comfyui_metadata_from_png(file_path)
            if metadata:
                # 检查不同位置的prompt内容
                prompt_text = json.dumps(metadata)

                if keyword.lower() in prompt_text.lower():
                    found_count += 1
                    print(filename)
                    _LOGGER.debug(
                        f"完整元数据:\n{json.dumps(metadata, indent=2, ensure_ascii=False)}"
                    )

    _LOGGER.info(f"搜索完成，共找到 {found_count} 个匹配结果")


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="搜索包含指定关键词的ComfyUI生成的PNG图片",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("keyword", type=str, help="要搜索的关键词")
    parser.add_argument(
        "-d", "--directory", type=str, default=".", help="要搜索的目录路径"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示完整的元数据")

    args = parser.parse_args()
    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    if not os.path.isdir(args.directory):
        _LOGGER.info(f"错误: 目录 '{args.directory}' 不存在")
        return

    find_pngs_with_prompt(
        keyword=args.keyword,
        directory=args.directory,
    )


if __name__ == "__main__":
    main()
