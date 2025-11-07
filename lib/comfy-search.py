import os
import argparse
import json
from PIL import Image
from typing import Dict, Optional, TypedDict, Set

import logging

_LOGGER = logging.getLogger(__name__)


class PromptValueInputs(TypedDict):
    text: str
    clip: list[str]
    ckpt_name: str
    width: int
    height: int
    batch_size: int
    samples: list[str]
    vae: list[str]
    filename_prefix: str
    images: list[str]
    seed: int
    steps: int
    cfg: float
    sampler_name: str
    scheduler: str
    denoise: float
    basic_pipe: list[str]
    latent_image: list[str]
    image: str
    conditioning_to: list[str]
    conditioning_from: list[str]


class PromptValue(TypedDict):
    inputs: PromptValueInputs
    class_type: str
    _meta: Dict[str, str]


# ComfyUI 输出文件的元数据结构
# key 为 node id，value 为 PromptValue
Prompt = Dict[str, PromptValue]


def extract_prompt_from_png(file_path: str) -> Optional[Prompt]:
    """从PNG文件中提取ComfyUI元数据"""
    try:
        with Image.open(file_path) as img:
            # show image info
            # ComfyUI 将元数据存储在 "prompt" 文本块中
            if "prompt" in img.info:
                return json.loads(img.info["prompt"])
    except Exception as e:
        _LOGGER.error(f"Error reading {file_path}: {e}")


def find_pngs_with_prompt(
    keyword: str,
    directory: str = ".",
    node_ids: Optional[Set[str]] = None,
    case_sensitive: bool = False,
) -> None:
    """在指定目录查找包含关键词的PNG图片"""
    found_count = 0
    search_func = str.__contains__ if case_sensitive else lambda s, k: k in s.lower()
    keyword = keyword if case_sensitive else keyword.lower()

    for filename in os.listdir(directory):
        if not filename.lower().endswith(".png"):
            continue

        file_path = os.path.join(directory, filename)
        prompt_data = extract_prompt_from_png(file_path)
        if not prompt_data:
            continue

        # 遍历所有节点或指定节点
        for node_id, node_value in prompt_data.items():
            if node_ids and node_id not in node_ids:
                continue

            try:
                text = node_value["inputs"]["text"]
                text_to_search = text if case_sensitive else text.lower()
                if search_func(text_to_search, keyword):
                    found_count += 1
                    print(filename)  # output to stdout
                    _LOGGER.debug(f"节点 {node_id} 内容: {text}")
                    break  # 找到即停止当前文件检查
            except KeyError:
                continue

    _LOGGER.info(f"搜索完成，共找到 {found_count} 个匹配结果")


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="ComfyUI PNG元数据搜索工具",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("keyword", help="要搜索的关键词")
    parser.add_argument("-d", "--directory", default=".", help="搜索目录")
    parser.add_argument("-n", "--node-ids", help="指定要检查的节点ID（逗号分隔）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示调试信息")
    parser.add_argument(
        "-c", "--case-sensitive", action="store_true", help="区分大小写"
    )

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    # 处理节点ID参数
    node_ids = set(args.node_ids.split(",")) if args.node_ids else None

    if not os.path.isdir(args.directory):
        _LOGGER.error(f"目录不存在: {args.directory}")
        return

    find_pngs_with_prompt(
        keyword=args.keyword,
        directory=args.directory,
        node_ids=node_ids,
        case_sensitive=args.case_sensitive,
    )


if __name__ == "__main__":
    main()
