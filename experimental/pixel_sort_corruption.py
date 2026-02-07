#!/usr/bin/env python3

import argparse
from typing import Optional, List, Tuple, Iterator
from PIL import Image
import numpy as np
import random
import logging
import contextlib

_LOGGER = logging.getLogger(__name__)


class _Context:
    """
    像素排序损坏的上下文类，用于管理所有相关参数和状态
    """

    def __init__(
        self,
        image: Image.Image,
        edge_guide: Optional[Image.Image] = None,
        intensity: float = 0.3,
        x_jitter: int = 15,
        sort_method: str = "euclidean",
        seed: int = -1,
        y_span: int = 1,
        block_size: int = 1,
        angle: float = 0.0,
        quality_scale: float = 1,
    ):

        self.raw_image = image
        self.raw_edge_guide = edge_guide
        self.intensity = min(1, max(0, intensity))
        self.x_jitter = x_jitter
        self.sort_method = sort_method
        self.seed = seed
        self.y_span = max(1, int(y_span * quality_scale))
        self.block_size = max(1, int(block_size * quality_scale))
        self.angle = angle
        self.quality_scale = max(1, quality_scale)

        # 创建局部随机状态
        self.rng = random.Random(seed if seed >= 0 else None)

        # 处理后的图像和状态
        self.image: Optional[Tuple[Image.Image, np.ndarray]] = None
        self.edge_guide: Optional[Tuple[Image.Image, np.ndarray]] = None
        self.mask: Optional[Tuple[Image.Image, np.ndarray]] = None

    def pre_process(self) -> None:
        image = self.raw_image
        if self.quality_scale > 1:
            # 放大图像
            new_size = (
                int(self.raw_image.width * self.quality_scale),
                int(self.raw_image.height * self.quality_scale),
            )
            image = self.raw_image.resize(new_size, Image.Resampling.LANCZOS)

        mask = Image.new("L", image.size, 255)
        edge_guide = self.raw_edge_guide
        if edge_guide:
            edge_guide = edge_guide.convert("L").resize(image.size)

        # 旋转图像（扩大画布）
        image = image.rotate(
            self.angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=0
        )
        self.image = (image, np.array(image))
        mask = mask.rotate(
            self.angle,
            expand=True,
            resample=Image.Resampling.NEAREST,
            fillcolor=0,
        )
        self.mask = (mask, np.array(mask))
        if edge_guide:
            edge_guide = edge_guide.rotate(
                self.angle, expand=True, resample=Image.Resampling.NEAREST, fillcolor=0
            )
            self.edge_guide = (edge_guide, np.array(edge_guide))

    def post_process(self, image: Image.Image) -> Image.Image:
        large_image = image.rotate(
            -self.angle, expand=True, resample=Image.Resampling.BICUBIC
        )

        large_image_width, large_image_height = (
            self.raw_image.width * self.quality_scale,
            self.raw_image.height * self.quality_scale,
        )
        left = (large_image.width - large_image_width) // 2
        top = (large_image.height - large_image_height) // 2
        right = left + large_image_width
        bottom = top + large_image_height

        # 裁剪
        cropped = large_image.crop((left, top, right, bottom))

        # 如果之前放大了，现在缩小回原始尺寸
        if self.quality_scale > 1:
            cropped = cropped.resize(self.raw_image.size, Image.Resampling.LANCZOS)

        return cropped

    def corrupted_rows(self) -> Iterator[int]:
        """
        选择需要损坏的行，考虑最小连续行数要求
        返回损坏行的迭代器
        """
        assert self.image

        height = self.image[1].shape[0]

        target_density = self.intensity

        if self.intensity < 1 and self.edge_guide:
            # 计算被引导图排除的行数（全黑行不参与损坏）
            # 引导可能排除行，所以剩余行需要使用更高的比例以保持总体密度符合预期
            exclude_row_count = sum(
                1 for row in range(height) if np.all(self.edge_guide[1][row, :] == 0)
            )
            valid_row_count = height - exclude_row_count
            if valid_row_count > 0:
                target_density *= height / valid_row_count
            else:
                target_density = 0

        target_density = min(1.0, max(0.0, target_density))

        if target_density >= 1:
            corruption_probability = 1.0
        elif self.y_span <= 1:
            corruption_probability = target_density
        else:
            # 使用修正公式计算概率
            # p = D / (L - D(L-1))
            # 其中 D 是目标密度，L 是 y_span
            # 修正 y_span > 1 时由于连续块互斥导致的实际密度偏低的问题
            corruption_probability = target_density / (
                self.y_span - target_density * (self.y_span - 1)
            )

        index = 0
        last_corruption_start = -1
        while index < height:

            corrupted = corruption_probability >= 1 or (
                last_corruption_start >= 0
                and index < last_corruption_start + self.y_span
            )

            if not corrupted:
                corrupted = self.rng.random() < corruption_probability
                if corrupted:
                    # 开始损坏
                    last_corruption_start = index

            if (
                corrupted
                and self.edge_guide
                and not np.any(self.edge_guide[1][index, :] > 0)
            ):
                # 引导中断损坏
                corrupted = False
                last_corruption_start = -1

            if corrupted:
                yield index
            index += 1

    def group_rows_into_blocks(
        self, corrupted_rows: Iterator[int]
    ) -> Iterator[List[int]]:
        """
        将损坏的行分组为连续块，每个块大小不超过block_size
        """
        current_block: List[int] = []

        for row in corrupted_rows:
            if not current_block:
                # 开始新块
                current_block.append(row)
            elif row == current_block[-1] + 1 and len(current_block) < self.block_size:
                # 行连续且块未满，添加到当前块
                current_block.append(row)
            else:
                # 行不连续或块已满，返回当前块并开始新块
                yield current_block
                current_block = [row]

        # 返回最后一个块
        if current_block:
            yield current_block

    def calculate_left(
        self, block_rows: List[int], previous_left: Optional[int]
    ) -> Optional[int]:
        """计算block的起始x坐标"""

        assert self.image
        assert self.mask

        width = self.image[0].width

        if self.edge_guide:
            # 边缘引导图模式：基于引导图非黑色区域的最左侧位置
            non_black_indices = np.where(self.edge_guide[1][block_rows[0], :] > 0)[0]
            if len(non_black_indices) > 0:
                base_x = non_black_indices[0]
                jitter = self.rng.randint(-self.x_jitter, self.x_jitter)
                left = max(0, min(width - 10, base_x + jitter))
                return left
            return 0

        # 无边缘引导图模式：
        row_mask = self.mask[1][block_rows[0], :]
        original_pixel_indices = np.where(row_mask > 0)[0]
        if len(original_pixel_indices) == 0:
            return None

        min_x = original_pixel_indices[0]
        max_x = original_pixel_indices[-1]
        if previous_left is not None:
            # 基于上次位置限制范围
            min_x = max(min_x, previous_left - self.x_jitter)
            max_x = min(max_x, previous_left + self.x_jitter)
            if min_x > max_x:
                # 无法满足限制，不抖动
                return previous_left
        return self.rng.randint(min_x, max_x)

    def corrupted_blocks(self) -> Iterator[Tuple[List[int], int]]:
        """
        统一的行和block选择逻辑
        结合行选择和分组功能
        """
        # 选择需要损坏的行
        corrupted_rows = self.corrupted_rows()

        # 将行分组为块
        blocks = self.group_rows_into_blocks(corrupted_rows)

        # 为每个块计算起始位置
        previous_left = None
        for block_rows in blocks:
            left = self.calculate_left(block_rows, previous_left)
            if left is not None:
                yield (block_rows, left)
            previous_left = left

    def calculate_brightness(self, pixels: np.ndarray) -> np.ndarray:
        """
        计算像素的亮度值
        对于彩色图像使用标准亮度公式，对于灰度图像直接使用像素值
        """
        if pixels.ndim > 1 and pixels.shape[-1] >= 3:  # 彩色图像
            # 标准亮度公式: 0.299*R + 0.587*G + 0.114*B
            brightness = (
                0.299 * pixels[..., 0] + 0.587 * pixels[..., 1] + 0.114 * pixels[..., 2]
            )
        else:  # 灰度图像
            brightness = pixels

        return brightness

    def measure_distances(
        self,
        pixels: np.ndarray,
        pixel_mask: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        assert self.image

        ref_pixel = pixels[0]

        # 只处理标记为原始图像的像素
        valid_indices = np.where(pixel_mask > 0)[0]

        if len(valid_indices) == 0:
            return np.array([]), np.array([])

        valid_pixels = pixels[valid_indices]

        # 新增的基于像素本身的排序方法（在原有方法之前拦截）
        if self.sort_method in ["dark-to-light", "light-to-dark"]:
            # 计算亮度值
            brightness = self.calculate_brightness(valid_pixels)

            if self.sort_method == "dark-to-light":
                # 从暗到亮：直接使用亮度值
                distances = brightness
            else:  # light-to-dark
                # 从亮到暗：使用亮度值的负数
                distances = -brightness

            return distances, valid_indices

        # 确定通道数
        channels = self.image[1].shape[2] if self.image[1].ndim == 3 else 1

        # 处理不同通道数的图片
        if channels >= 3:  # 彩色图片（RGB或RGBA等）
            valid_pixels_rgb: np.ndarray
            ref_pixel_rgb: np.ndarray

            if valid_pixels.ndim > 1:
                valid_pixels_rgb = valid_pixels[:, :3]
            else:
                valid_pixels_rgb = valid_pixels[:3]

            ref_pixel_rgb = ref_pixel[:3]

            if self.sort_method == "euclidean":
                distances = np.sqrt(
                    np.sum((valid_pixels_rgb - ref_pixel_rgb) ** 2, axis=1)
                )
            elif self.sort_method == "manhattan":
                distances = np.sum(np.abs(valid_pixels_rgb - ref_pixel_rgb), axis=1)
            elif self.sort_method == "brightness":
                if valid_pixels_rgb.ndim > 1:
                    pixel_brightness = self.calculate_brightness(valid_pixels_rgb)
                    ref_brightness = self.calculate_brightness(ref_pixel_rgb)
                    distances = np.abs(pixel_brightness - ref_brightness)
                else:
                    distances = np.abs(valid_pixels_rgb - ref_pixel_rgb)
            else:
                raise ValueError("不支持的比较方法 %s", self.sort_method)
        else:
            # 灰度图
            distances = np.abs(valid_pixels - ref_pixel).flatten()

        return distances, valid_indices

    def process(self) -> Image.Image:
        self.pre_process()

        assert self.image
        assert self.mask

        # 创建副本进行操作

        width = self.image[0].width

        # 处理每个block
        for block_rows, left in self.corrupted_blocks():
            if left >= width - 1:
                continue

            ref_row = block_rows[0]

            if (
                self.angle != 0
                and len(block_rows) > 1
                and np.count_nonzero(self.mask[1][ref_row, left:])
                < np.count_nonzero(self.mask[1][block_rows[-1], left:])
            ):
                # 如果块的最后一行比第一行长，则使用最后一行数据
                ref_row = block_rows[-1]

            right_pixels = self.image[1][ref_row, left:]
            if len(right_pixels) > 1:
                right_pixel_mask = self.mask[1][ref_row, left:]
                # 计算距离（只考虑原始图像像素）
                distances, valid_indices = self.measure_distances(
                    right_pixels,
                    right_pixel_mask,
                )

                if len(distances) > 0:
                    # 按相似度排序
                    sorted_valid_indices = valid_indices[np.argsort(distances)]

                    # 创建排序后的像素数组（保持原始顺序，只重新排列有效像素）
                    sorted_pixels = right_pixels.copy()
                    sorted_pixels[valid_indices] = right_pixels[sorted_valid_indices]

                    # 将排序后的像素应用到block中的所有行
                    for row in block_rows:
                        self.image[1][row, left:] = sorted_pixels

        # 创建结果图像
        result_img = Image.fromarray(self.image[1])

        return self.post_process(image=result_img)


def pixel_sort_corruption(
    image: Image.Image,
    edge_guide: Optional[Image.Image] = None,
    intensity: float = 0.3,
    x_jitter: int = 15,
    sort_method: str = "euclidean",
    seed: int = -1,
    y_span: int = 1,
    block_size: int = 1,
    angle: float = 0.0,
    quality_scale: float = 1,
) -> Image.Image:
    """
    高级相似度损坏效果，支持边缘引导图、强度控制和任意角度

    参数:
        image: 输入图像
        edge_guide: 边缘引导图（可选）
        intensity: 损坏强度（0-1）
        x_jitter: 水平抖动范围
        sort_method: 排序方法，包括:
            - "euclidean": 欧几里得距离
            - "manhattan": 曼哈顿距离
            - "brightness": 亮度相似度
            - "dark-to-light": 从暗到亮排序
            - "light-to-dark": 从亮到暗排序
        seed: 随机种子
        y_span: 垂直跨度
        block_size: 块大小
        angle: 旋转角度
        quality_scale: 质量缩放因子

    返回:
        处理后的图像
    """
    # 创建上下文并处理
    context = _Context(
        image=image,
        edge_guide=edge_guide,
        intensity=intensity,
        x_jitter=x_jitter,
        sort_method=sort_method,
        seed=seed,
        y_span=y_span,
        block_size=block_size,
        angle=angle,
        quality_scale=quality_scale,
    )

    return context.process()


def main() -> None:
    """主函数"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="应用像素排序损坏效果到图片",
    )

    # 必需参数
    parser.add_argument("input", help="输入图片路径")
    parser.add_argument("output", help="输出图片路径")

    # 可选参数
    parser.add_argument(
        "-e",
        "--edge-guide",
        dest="edge_guide_path",
        help="边缘引导图文件路径（可选）。如果提供，效果将应用于引导图非黑色区域",
    )

    parser.add_argument(
        "-i",
        "--intensity",
        dest="intensity",
        type=float,
        default=0.3,
        help="效果强度（0-1之间的浮点数）。在无引导图模式下，指定要处理的行的比例。默认: 0.3",
    )

    parser.add_argument(
        "-j",
        "--x-jitter",
        dest="x_jitter",
        type=int,
        default=15,
        help="最大水平抖动范围（像素）。控制起始点水平抖动的最大范围。默认: 15",
    )

    parser.add_argument(
        "-s",
        "--sort",
        dest="sort_method",
        choices=[
            "euclidean",
            "manhattan",
            "brightness",
            "dark-to-light",
            "light-to-dark",
        ],
        default="euclidean",
        help="排序方法。可选: euclidean(欧几里得距离), manhattan(曼哈顿距离), brightness(亮度相似度), dark-to-light(从暗到亮), light-to-dark(从亮到暗)。默认: euclidean",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="随机种子。固定种子以获得可重现的结果。使用-1表示使用随机种子（默认）。",
    )

    parser.add_argument(
        "--y-span",
        dest="y_span",
        type=int,
        default=1,
        help="垂直跨度。一旦某行被损坏，下面n-1行也跟着被损坏。默认: 1",
    )

    parser.add_argument(
        "--block-size",
        dest="block_size",
        type=int,
        default=1,
        help="块大小。将连续的多行视为一个块处理，使用第一行的像素数据。默认: 1",
    )

    parser.add_argument(
        "-a",
        "--angle",
        type=float,
        default=0.0,
        help="损坏方向的角度（度数）。0度表示水平向右，90度表示垂直向下。默认: 0.0",
    )

    parser.add_argument(
        "-q",
        "--quality-scale",
        type=int,
        default=1,
        help="质量缩放因子。在旋转前放大图像以提高精度，处理后再缩小。值越大精度越高但速度越慢。默认: 1（不缩放）",
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

    # 参数验证
    if args.quality_scale < 1:
        parser.error("质量缩放因子必须大于等于1")

    # 执行
    with Image.open(args.input) as input_image, (
        Image.open(args.edge_guide_path)
        if args.edge_guide_path
        else contextlib.nullcontext()
    ) as edge_guide_image:
        result_image: Image.Image = pixel_sort_corruption(
            image=input_image,
            edge_guide=edge_guide_image if args.edge_guide_path else None,
            intensity=args.intensity,
            x_jitter=args.x_jitter,
            sort_method=args.sort_method,
            seed=args.seed,
            y_span=args.y_span,
            block_size=args.block_size,
            angle=args.angle,
            quality_scale=args.quality_scale,
        )

    # 保存结果
    result_image.save(args.output)
    _LOGGER.info(f"处理成功完成! 结果保存至: {args.output}")


if __name__ == "__main__":
    main()
