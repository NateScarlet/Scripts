#!/usr/bin/env python3

import argparse
from typing import Optional, List, Tuple, Iterator
from PIL import Image
import numpy as np
import random
import logging
import contextlib

_LOGGER = logging.getLogger(__name__)


def pixel_sort_corruption(
    image: Image.Image,
    mask: Optional[Image.Image] = None,
    corruption_ratio: float = 0.3,
    max_jitter: int = 15,
    similarity_method: str = "euclidean",
    seed: int = -1,
    min_consecutive_rows: int = 1,
    chunk_size: int = 1,
) -> Image.Image:
    """
    高级相似度损坏效果，支持蒙版和损坏比例控制

    参数:
    ◦ image: 输入PIL图像
    ◦ mask: 蒙版图像（可选，如提供则使用蒙版确定起始点）
    ◦ corruption_ratio: 损坏比例（0-1之间，表示多少比例的行会被处理）
    ◦ max_jitter: 起始点的最大抖动范围
    ◦ similarity_method: 相似度计算方法 ('euclidean', 'manhattan', 'brightness')
    ◦ seed: 随机种子，-1表示使用随机种子
    ◦ min_consecutive_rows: 最小连续行数，一旦选中某行，必须连续处理下面n-1行
    ◦ chunk_size: 一次处理的行数，将多行视为一个块处理

    返回:
    ◦ 处理后的PIL图像
    """
    corruption_ratio = min(1, max(0, corruption_ratio))
    min_consecutive_rows = max(1, min_consecutive_rows)
    chunk_size = max(1, chunk_size)

    # 创建局部随机状态，避免影响全局随机状态
    rng: random.Random = random.Random(seed if seed >= 0 else None)

    # 将图像转换为numpy数组
    img_array: np.ndarray = np.array(image)

    # 处理图片维度问题
    height: int
    width: int
    channels: int
    if img_array.ndim == 2:  # 灰度图片
        height, width = img_array.shape
        channels = 1
        # 转换为三维数组以便统一处理
        img_array = img_array[:, :, np.newaxis]
    else:  # 彩色图片
        height, width, channels = img_array.shape

    if max_jitter < 0:
        max_jitter = width
    else:
        max_jitter = min(width, max_jitter)

    # 处理蒙版图像
    mask_array: Optional[np.ndarray] = None
    if mask is not None:
        mask_gray: Image.Image = mask.convert("L")  # 转换为灰度
        mask_array = np.array(mask_gray)
        # 确保蒙版尺寸与主图一致
        if mask_array.shape != (height, width):
            mask_resized: Image.Image = mask_gray.resize((width, height))
            mask_array = np.array(mask_resized)

    # 创建副本进行操作
    corrupted_array: np.ndarray = img_array.copy()

    # 定义相似度计算方法
    def calculate_similarity(
        pixels: np.ndarray, ref_pixel: np.ndarray, method: str, num_channels: int
    ) -> np.ndarray:
        """
        计算像素相似度

        参数:
        ◦ pixels: 像素数组
        ◦ ref_pixel: 参考像素
        ◦ method: 相似度计算方法
        ◦ num_channels: 通道数

        返回:
        ◦ 相似度距离数组
        """
        # 处理不同通道数的图片
        if num_channels >= 3:  # 彩色图片（RGB或RGBA等）
            # 只使用前3个通道计算相似度（忽略alpha通道等）
            pixels_rgb: np.ndarray
            ref_pixel_rgb: np.ndarray

            if pixels.ndim > 1:
                pixels_rgb = pixels[:, :3]
            else:
                pixels_rgb = pixels[:3]

            ref_pixel_rgb = ref_pixel[:3]

            if method == "euclidean":
                return np.sqrt(np.sum((pixels_rgb - ref_pixel_rgb) ** 2, axis=1))

            elif method == "manhattan":
                return np.sum(np.abs(pixels_rgb - ref_pixel_rgb), axis=1)

            elif method == "brightness":
                # 计算亮度（使用标准亮度公式）
                if pixels_rgb.ndim > 1:
                    pixel_brightness: np.ndarray = (
                        0.299 * pixels_rgb[:, 0]
                        + 0.587 * pixels_rgb[:, 1]
                        + 0.114 * pixels_rgb[:, 2]
                    )
                    ref_brightness: float = (
                        0.299 * ref_pixel_rgb[0]
                        + 0.587 * ref_pixel_rgb[1]
                        + 0.114 * ref_pixel_rgb[2]
                    )
                    return np.abs(pixel_brightness - ref_brightness)
                else:
                    return np.abs(pixels_rgb - ref_pixel_rgb)

        # 默认情况
        return np.abs(pixels - ref_pixel).flatten()

    # 统一的行选择逻辑
    def select_rows_and_chunks() -> Iterator[Tuple[List[int], int]]:
        """
        统一的行和chunk选择逻辑

        返回:
        ◦ 列表，每个元素为 (该chunk包含的所有行, 起始x坐标)
        """
        # 步骤1: 确定候选行
        candidate_rows = list(range(height))

        # 如果有蒙版，排除蒙版中全黑的行
        if mask_array is not None:
            candidate_rows = [
                row for row in candidate_rows if np.any(mask_array[row, :] > 0)
            ]

        if not candidate_rows:
            return

        # 步骤2: 将候选行分组为连续的块
        consecutive_blocks: list[list[int]] = []
        current_block: list[int] = []

        for i, row in enumerate(candidate_rows):
            if not current_block:
                current_block.append(row)
            else:
                # 检查是否连续
                if row == current_block[-1] + 1:
                    current_block.append(row)
                else:
                    # 不连续，保存当前块并开始新块
                    if len(current_block) >= min_consecutive_rows:
                        consecutive_blocks.append(current_block)
                    current_block = [row]

        # 添加最后一个块
        if len(current_block) >= min_consecutive_rows:
            consecutive_blocks.append(current_block)

        # 步骤3: 计算需要选择的块数
        target_blocks = int(len(consecutive_blocks) * corruption_ratio)
        target_blocks = max(1, min(len(consecutive_blocks), target_blocks))

        # 随机选择块
        selected_blocks = rng.sample(consecutive_blocks, target_blocks)

        # 步骤4: 将选中的块按chunk_size分组并计算起始位置
        prev_start_x: Optional[int] = None

        for block in selected_blocks:
            # 将块按chunk_size分组
            for i in range(0, len(block), chunk_size):
                chunk_rows = block[i : i + chunk_size]
                if not chunk_rows:
                    continue

                # 计算该chunk的起始位置
                if mask_array is not None:
                    # 蒙版模式：基于蒙版非黑色区域的最左侧位置
                    non_black_indices = np.where(mask_array[chunk_rows[0], :] > 0)[0]
                    if len(non_black_indices) > 0:
                        base_x = non_black_indices[0]
                        jitter = rng.randint(-max_jitter, max_jitter)
                        start_x = max(0, min(width - 10, base_x + jitter))
                    else:
                        start_x = 0
                else:
                    # 无蒙版模式：基于上一chunk的位置加抖动
                    if prev_start_x is None:
                        max_start = max(0, width - 10)
                        start_x = rng.randint(0, max_start) if max_start >= 0 else 0
                    else:
                        jitter = rng.randint(-max_jitter, max_jitter)
                        start_x = max(0, min(width - 10, prev_start_x + jitter))
                    prev_start_x = start_x

                yield (chunk_rows, start_x)

    # 处理每个chunk
    for chunk_rows, start_x in select_rows_and_chunks():
        if start_x >= width - 1:
            continue

        # 使用chunk的第一行作为参考行
        ref_row = chunk_rows[0]

        # 提取参考像素和右侧像素
        reference_pixel: np.ndarray
        right_pixels: np.ndarray

        if channels == 1:
            reference_pixel = corrupted_array[ref_row, start_x]
            # 获取chunk中所有行的右侧像素并平均
            chunk_right_pixels = np.array(
                [corrupted_array[r, start_x:] for r in chunk_rows]
            )
            right_pixels = chunk_right_pixels.mean(axis=0)
        else:
            reference_pixel = corrupted_array[ref_row, start_x, :]
            chunk_right_pixels = np.array(
                [corrupted_array[r, start_x:, :] for r in chunk_rows]
            )
            right_pixels = chunk_right_pixels.mean(axis=0)

        if len(right_pixels) > 1:
            # 计算相似度（每个chunk只计算一次）
            distances: np.ndarray = calculate_similarity(
                right_pixels, reference_pixel, similarity_method, channels
            )

            # 按相似度排序（最相似的排在左边）
            sorted_indices: np.ndarray = np.argsort(distances)
            sorted_pixels: np.ndarray = right_pixels[sorted_indices]

            # 将排序后的像素应用到chunk中的所有行
            for row in chunk_rows:
                if channels == 1:
                    corrupted_array[row, start_x:] = sorted_pixels
                else:
                    corrupted_array[row, start_x:, :] = sorted_pixels

    # 恢复二维数组格式（如果是灰度图）
    if channels == 1:
        corrupted_array = corrupted_array[:, :, 0]

    # 创建结果图像
    result_img: Image.Image = Image.fromarray(corrupted_array.astype(np.uint8))
    return result_img


def main() -> None:
    """主函数"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="应用像素排序损坏效果到图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 无蒙版模式，损坏30%的行
  %(prog)s input.jpg output.jpg --ratio 0.3
  
  # 使用蒙版模式，指定抖动范围
  %(prog)s input.jpg output.jpg --mask mask.png --jitter 20
  
  # 使用曼哈顿距离作为相似度度量
  %(prog)s input.jpg output.jpg --ratio 0.5 --similarity manhattan
  
  # 高损坏比例，使用亮度相似度
  %(prog)s input.jpg output.jpg --ratio 0.8 --similarity brightness
  
  # 固定随机种子以获得可重现的结果
  %(prog)s input.jpg output.jpg --seed 42
  
  # 最小连续行3行，每次处理2行
  %(prog)s input.jpg output.jpg --min-consecutive 3 --chunk-size 2
        """,
    )

    # 必需参数
    parser.add_argument("input", help="输入图片路径")
    parser.add_argument("output", help="输出图片路径")

    # 可选参数
    parser.add_argument(
        "-m",
        "--mask",
        dest="mask_path",
        help="蒙版文件路径（可选）。如果提供，效果将应用于蒙版非黑色区域",
    )

    parser.add_argument(
        "-r",
        "--ratio",
        dest="corruption_ratio",
        type=float,
        default=0.3,
        help="损坏比例（0-1之间的浮点数）。在无蒙版模式下，指定要处理的行的比例。默认: 0.3",
    )

    parser.add_argument(
        "-j",
        "--jitter",
        dest="max_jitter",
        type=int,
        default=15,
        help="最大抖动范围（像素）。控制起始点水平抖动的最大范围。默认: 15",
    )

    parser.add_argument(
        "-s",
        "--similarity",
        dest="similarity_method",
        choices=["euclidean", "manhattan", "brightness"],
        default="euclidean",
        help="相似度计算方法。可选: euclidean(欧几里得距离), manhattan(曼哈顿距离), brightness(亮度相似度)。默认: euclidean",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="随机种子。固定种子以获得可重现的结果。使用-1表示使用随机种子（默认）。",
    )

    parser.add_argument(
        "--min-consecutive",
        dest="min_consecutive_rows",
        type=int,
        default=1,
        help="最小连续行数。一旦某行被选中，必须连续处理下面n-1行。默认: 1",
    )

    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        type=int,
        default=1,
        help="一次处理的行数。将多行视为一个块处理，使用第一行的像素数据。默认: 1",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细日志输出",
    )

    # 解析参数
    args: argparse.Namespace = parser.parse_args()

    # 配置日志
    log_level: int = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    # 执行
    with Image.open(args.input) as input_image, (
        Image.open(args.mask_path) if args.mask_path else contextlib.nullcontext()
    ) as mask_image:
        result_image: Image.Image = pixel_sort_corruption(
            image=input_image,
            mask=mask_image,
            corruption_ratio=args.corruption_ratio,
            max_jitter=args.max_jitter,
            similarity_method=args.similarity_method,
            seed=args.seed,
            min_consecutive_rows=args.min_consecutive_rows,
            chunk_size=args.chunk_size,
        )

    # 保存结果
    result_image.save(args.output, quality=95)
    _LOGGER.info(f"处理成功完成! 结果保存至: {args.output}")


if __name__ == "__main__":
    main()
