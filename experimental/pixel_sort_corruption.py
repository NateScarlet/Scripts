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
        mask: Optional[Image.Image] = None,
        corruption_ratio: float = 0.3,
        max_jitter: int = 15,
        similarity_method: str = "euclidean",
        seed: int = -1,
        min_consecutive_rows: int = 1,
        chunk_size: int = 1,
        angle: float = 0.0,
        upscale_factor: float = 1,
    ):

        self.image = image
        self.mask = mask
        self.corruption_ratio = min(1, max(0, corruption_ratio))
        self.max_jitter = max_jitter
        self.similarity_method = similarity_method
        self.seed = seed
        self.min_consecutive_rows = max(1, int(min_consecutive_rows * upscale_factor))
        self.chunk_size = max(1, int(chunk_size * upscale_factor))
        self.angle = angle
        self.upscale_factor = max(1, upscale_factor)

        # 创建局部随机状态
        self.rng = random.Random(seed if seed >= 0 else None)

        # 处理后的图像和状态
        self.processed_image: Optional[Image.Image] = None
        self.rotated_image: Optional[Image.Image] = None
        self.rotated_mask: Optional[Image.Image] = None
        self.rotated_original_mask: Optional[Image.Image] = None
        self.original_size: Optional[Tuple[int, int]] = None

        # 数组缓存
        self.img_array: Optional[np.ndarray] = None
        self.mask_array: Optional[np.ndarray] = None
        self.original_mask_array: Optional[np.ndarray] = None

    def create_original_pixel_mask(self) -> Image.Image:
        """
        创建标记原始图像像素的蒙版
        原始图像区域标记为255，旋转填充区域标记为0
        """
        if self.upscale_factor > 1:
            new_size = (
                int(self.image.width * self.upscale_factor),
                int(self.image.height * self.upscale_factor),
            )
            mask = Image.new("L", new_size, 255)  # 全白表示原始图像区域
        else:
            mask = Image.new("L", self.image.size, 255)

        return mask

    def rotate_image_and_mask(self) -> None:
        """
        旋转图像和蒙版，支持放大处理，并设置相关状态
        """
        # 创建原始像素标记蒙版
        original_pixel_mask = self.create_original_pixel_mask()

        if self.upscale_factor > 1:
            # 放大图像
            new_size = (
                int(self.image.width * self.upscale_factor),
                int(self.image.height * self.upscale_factor),
            )
            image_large = self.image.resize(new_size, Image.Resampling.LANCZOS)
            if self.mask is not None:
                mask_large = self.mask.resize(new_size, Image.Resampling.NEAREST)
            else:
                mask_large = None
        else:
            image_large = self.image
            mask_large = self.mask

        # 旋转图像（扩大画布以避免裁剪）
        self.rotated_image = image_large.rotate(
            self.angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=0
        )

        if mask_large is not None:
            self.rotated_mask = mask_large.rotate(
                self.angle, expand=True, resample=Image.Resampling.NEAREST, fillcolor=0
            )
        else:
            self.rotated_mask = None

        # 旋转原始像素标记蒙版
        self.rotated_original_mask = original_pixel_mask.rotate(
            self.angle,
            expand=True,
            resample=Image.Resampling.NEAREST,  # 使用最近邻保持清晰的边界
            fillcolor=0,  # 填充区域标记为0
        )

        self.original_size = image_large.size

    def unrotate_image(self, image: Image.Image) -> Image.Image:
        """
        将图像旋转回原始方向并裁剪
        """
        if self.original_size is None:
            raise ValueError("必须先调用 rotate_image_and_mask()")

        # 旋转回原始方向
        unrotated = image.rotate(
            -self.angle, expand=False, resample=Image.Resampling.BICUBIC
        )

        # 计算裁剪区域（居中裁剪）
        center_x, center_y = unrotated.width // 2, unrotated.height // 2
        orig_width, orig_height = self.original_size
        left = center_x - orig_width // 2
        top = center_y - orig_height // 2
        right = left + orig_width
        bottom = top + orig_height

        # 确保裁剪区域在图像范围内
        left = max(0, left)
        top = max(0, top)
        right = min(unrotated.width, right)
        bottom = min(unrotated.height, bottom)

        cropped = unrotated.crop((left, top, right, bottom))

        if self.upscale_factor > 1:
            # 缩小回原始尺寸
            original_actual_size = (
                int(orig_width / self.upscale_factor),
                int(orig_height / self.upscale_factor),
            )
            cropped = cropped.resize(original_actual_size, Image.Resampling.LANCZOS)

        return cropped

    def corrupted_rows(self) -> Iterator[int]:
        """
        选择需要损坏的行，考虑最小连续行数要求
        返回损坏行的迭代器
        """
        if self.img_array is None:
            raise ValueError("必须先设置img_array")

        height = self.img_array.shape[0]

        # 确定候选行
        candidate_rows = list(range(height))

        # 如果有蒙版，排除蒙版中全黑的行
        if self.mask_array is not None:
            candidate_rows = [
                row for row in candidate_rows if np.any(self.mask_array[row, :] > 0)
            ]

        if not candidate_rows:
            return

        # 计算目标损坏行数
        target_total_rows = int(len(candidate_rows) * self.corruption_ratio)
        target_total_rows = max(1, min(len(candidate_rows), target_total_rows))

        _LOGGER.debug(
            f"候选行数: {len(candidate_rows)}, 目标损坏行数: {target_total_rows}"
        )

        # 逐行选择，考虑连续行要求
        corrupted_count = 0  # 已损坏行数
        current_index = 0  # 当前处理的候选行索引

        while (
            current_index < len(candidate_rows) and corrupted_count < target_total_rows
        ):
            remaining_rows = len(candidate_rows) - current_index
            remaining_target = target_total_rows - corrupted_count

            # 如果必须选择所有剩余行才能达到目标
            if remaining_target == remaining_rows:
                # 选择当前行及其后续的连续行
                chunk_size_actual = min(self.min_consecutive_rows, remaining_target)
                for i in range(chunk_size_actual):
                    if current_index + i < len(candidate_rows):
                        yield candidate_rows[current_index + i]
                        corrupted_count += 1
                current_index += chunk_size_actual
                continue

            # 计算当前行的选择概率
            selection_probability = remaining_target / remaining_rows

            # 决定是否选择当前行
            if self.rng.random() < selection_probability:
                # 选择当前行及其后续的连续行
                chunk_size_actual = min(self.min_consecutive_rows, remaining_target)
                for i in range(chunk_size_actual):
                    if current_index + i < len(candidate_rows):
                        yield candidate_rows[current_index + i]
                        corrupted_count += 1
                current_index += chunk_size_actual
            else:
                # 跳过当前行
                current_index += 1

        _LOGGER.debug(f"实际损坏行数: {corrupted_count}")

    def group_rows_into_chunks(
        self, corrupted_rows: Iterator[int]
    ) -> Iterator[List[int]]:
        """
        将损坏的行分组为连续块，每个块大小不超过chunk_size
        """
        current_chunk: List[int] = []

        for row in corrupted_rows:
            if not current_chunk:
                # 开始新块
                current_chunk.append(row)
            elif row == current_chunk[-1] + 1 and len(current_chunk) < self.chunk_size:
                # 行连续且块未满，添加到当前块
                current_chunk.append(row)
            else:
                # 行不连续或块已满，返回当前块并开始新块
                yield current_chunk
                current_chunk = [row]

        # 返回最后一个块
        if current_chunk:
            yield current_chunk

    def calculate_start_x(self, chunk_rows: List[int]) -> Optional[int]:
        """计算chunk的起始x坐标"""
        if not chunk_rows or self.img_array is None:
            return None

        width = self.img_array.shape[1]

        if self.mask_array is not None:
            # 蒙版模式：基于蒙版非黑色区域的最左侧位置
            non_black_indices = np.where(self.mask_array[chunk_rows[0], :] > 0)[0]
            if len(non_black_indices) > 0:
                base_x = non_black_indices[0]
                jitter = self.rng.randint(-self.max_jitter, self.max_jitter)
                start_x = max(0, min(width - 10, base_x + jitter))
                return start_x
            return 0

        # 无蒙版模式：基于原始像素区域选择起始点
        if self.original_mask_array is not None:
            # 如果有原始像素标记蒙版，确保起始点在原始像素区域内
            row_mask = self.original_mask_array[chunk_rows[0], :]
            original_pixel_indices = np.where(row_mask > 0)[0]

            if len(original_pixel_indices) > 0:
                # 在原始像素区域内选择起始点
                min_x = original_pixel_indices[0]
                max_x = original_pixel_indices[-1]

                # 随机选择起始点，但限制在原始像素区域内
                safe_max = min(max_x, width - 10)
                if safe_max > min_x:
                    return self.rng.randint(min_x, safe_max)
                return min_x
            return None

        # 没有原始像素标记蒙版，随机选择起始点
        max_start = max(0, width - 10)
        return self.rng.randint(0, max_start) if max_start >= 0 else 0

    def corrupted_chunks(self) -> Iterator[Tuple[List[int], int]]:
        """
        统一的行和chunk选择逻辑
        结合行选择和分组功能
        """
        # 选择需要损坏的行
        corrupted_rows = self.corrupted_rows()

        # 将行分组为块
        chunks = self.group_rows_into_chunks(corrupted_rows)

        # 为每个块计算起始位置
        for chunk_rows in chunks:
            start_x = self.calculate_start_x(chunk_rows)
            if start_x is not None:
                yield (chunk_rows, start_x)

    def similarity(
        self, pixels: np.ndarray, pixel_mask: np.ndarray, ref_pixel: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算像素相似度，只考虑原始图像像素（标记为1的像素）
        """
        if self.img_array is None:
            return np.array([]), np.array([])

        # 确定通道数
        channels = self.img_array.shape[2] if self.img_array.ndim == 3 else 1

        # 只处理标记为原始图像的像素
        valid_indices = np.where(pixel_mask > 0)[0]

        if len(valid_indices) == 0:
            return np.array([]), np.array([])

        valid_pixels = pixels[valid_indices]

        # 处理不同通道数的图片
        if channels >= 3:  # 彩色图片（RGB或RGBA等）
            valid_pixels_rgb: np.ndarray
            ref_pixel_rgb: np.ndarray

            if valid_pixels.ndim > 1:
                valid_pixels_rgb = valid_pixels[:, :3]
            else:
                valid_pixels_rgb = valid_pixels[:3]

            ref_pixel_rgb = ref_pixel[:3]

            if self.similarity_method == "euclidean":
                distances = np.sqrt(
                    np.sum((valid_pixels_rgb - ref_pixel_rgb) ** 2, axis=1)
                )
            elif self.similarity_method == "manhattan":
                distances = np.sum(np.abs(valid_pixels_rgb - ref_pixel_rgb), axis=1)
            elif self.similarity_method == "brightness":
                if valid_pixels_rgb.ndim > 1:
                    pixel_brightness: np.ndarray = (
                        0.299 * valid_pixels_rgb[:, 0]
                        + 0.587 * valid_pixels_rgb[:, 1]
                        + 0.114 * valid_pixels_rgb[:, 2]
                    )
                    ref_brightness: float = (
                        0.299 * ref_pixel_rgb[0]
                        + 0.587 * ref_pixel_rgb[1]
                        + 0.114 * ref_pixel_rgb[2]
                    )
                    distances = np.abs(pixel_brightness - ref_brightness)
                else:
                    distances = np.abs(valid_pixels_rgb - ref_pixel_rgb)
            else:
                raise ValueError("不支持的比较方法 %s", self.similarity_method)
        else:
            # 灰度图
            distances = np.abs(valid_pixels - ref_pixel).flatten()

        return distances, valid_indices

    def process_with_mask(self) -> Image.Image:
        """
        像素排序损坏的核心实现（水平方向），支持原始像素标记蒙版
        """
        # 确定要处理的图像
        if self.rotated_image is not None:
            image_to_process = self.rotated_image
            mask_to_process = self.rotated_mask
            original_mask_to_process = self.rotated_original_mask
        else:
            image_to_process = self.image
            mask_to_process = self.mask
            original_mask_to_process = None

        # 将图像转换为numpy数组
        self.img_array = np.array(image_to_process)

        # 处理图片维度问题
        height: int
        width: int
        channels: int
        if self.img_array.ndim == 2:  # 灰度图片
            height, width = self.img_array.shape
            channels = 1
            # 转换为三维数组以便统一处理
            self.img_array = self.img_array[:, :, np.newaxis]
        else:  # 彩色图片
            height, width, channels = self.img_array.shape

        if self.max_jitter < 0:
            self.max_jitter = width
        else:
            self.max_jitter = min(width, self.max_jitter)

        # 处理蒙版图像
        self.mask_array = None
        if mask_to_process is not None:
            mask_gray: Image.Image = mask_to_process.convert("L")  # 转换为灰度
            self.mask_array = np.array(mask_gray)
            # 确保蒙版尺寸与主图一致
            if self.mask_array.shape[:2] != (height, width):
                mask_resized: Image.Image = mask_gray.resize((width, height))
                self.mask_array = np.array(mask_resized)

        # 处理原始像素标记蒙版
        self.original_mask_array = None
        if original_mask_to_process is not None:
            original_mask_gray: Image.Image = original_mask_to_process.convert("L")
            self.original_mask_array = np.array(original_mask_gray)
            if self.original_mask_array.shape[:2] != (height, width):
                original_mask_resized: Image.Image = original_mask_gray.resize(
                    (width, height)
                )
                self.original_mask_array = np.array(original_mask_resized)

        # 创建副本进行操作
        corrupted_array: np.ndarray = self.img_array.copy()

        # 处理每个chunk
        for chunk_rows, start_x in self.corrupted_chunks():
            if start_x >= width - 1:
                continue

            # 使用chunk的第一行作为参考行
            ref_row = chunk_rows[0]

            # 提取参考像素和右侧像素
            reference_pixel: np.ndarray
            right_pixels: np.ndarray
            right_pixel_mask: np.ndarray

            if channels == 1:
                reference_pixel = corrupted_array[ref_row, start_x]
                # 获取chunk中所有行的右侧像素并平均
                chunk_right_pixels = np.array(
                    [corrupted_array[r, start_x:] for r in chunk_rows]
                )
                right_pixels = chunk_right_pixels.mean(axis=0)

                # 获取右侧像素的标记蒙版
                if self.original_mask_array is not None:
                    chunk_mask_pixels = np.array(
                        [self.original_mask_array[r, start_x:] for r in chunk_rows]
                    )
                    right_pixel_mask = chunk_mask_pixels.max(
                        axis=0
                    )  # 如果任何一行标记为原始像素，就认为是原始像素
                else:
                    right_pixel_mask = np.ones_like(
                        right_pixels
                    )  # 如果没有标记蒙版，全部视为原始像素
            else:
                reference_pixel = corrupted_array[ref_row, start_x, :]
                chunk_right_pixels = np.array(
                    [corrupted_array[r, start_x:, :] for r in chunk_rows]
                )
                right_pixels = chunk_right_pixels.mean(axis=0)

                if self.original_mask_array is not None:
                    chunk_mask_pixels = np.array(
                        [self.original_mask_array[r, start_x:] for r in chunk_rows]
                    )
                    right_pixel_mask = chunk_mask_pixels.max(axis=0)
                else:
                    right_pixel_mask = np.ones(right_pixels.shape[0])  # type: ignore

            if len(right_pixels) > 1:
                # 计算相似度（只考虑原始图像像素）
                distances, valid_indices = self.similarity(
                    right_pixels,
                    right_pixel_mask,  # type: ignore
                    reference_pixel,
                )

                if len(distances) > 0:
                    # 按相似度排序（最相似的排在左边）
                    sorted_valid_indices = valid_indices[np.argsort(distances)]

                    # 创建排序后的像素数组（保持原始顺序，只重新排列有效像素）
                    sorted_pixels = right_pixels.copy()
                    sorted_pixels[valid_indices] = right_pixels[sorted_valid_indices]

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

    def process(self) -> Image.Image:
        """
        主处理函数
        """
        # 如果角度为0且不需要放大，直接处理
        if self.angle == 0 and self.upscale_factor == 1:
            self.processed_image = self.process_with_mask()
            return self.processed_image

        # 旋转处理
        self.rotate_image_and_mask()

        # 在旋转后的图像上应用像素排序
        processed_rotated = self.process_with_mask()

        # 旋转回原始方向并裁剪
        self.processed_image = self.unrotate_image(processed_rotated)

        return self.processed_image


def pixel_sort_corruption(
    image: Image.Image,
    mask: Optional[Image.Image] = None,
    corruption_ratio: float = 0.3,
    max_jitter: int = 15,
    similarity_method: str = "euclidean",
    seed: int = -1,
    min_consecutive_rows: int = 1,
    chunk_size: int = 1,
    angle: float = 0.0,
    upscale_factor: float = 1,
) -> Image.Image:
    """
    高级相似度损坏效果，支持蒙版、损坏比例控制和任意角度
    """
    # 创建上下文并处理
    context = _Context(
        image=image,
        mask=mask,
        corruption_ratio=corruption_ratio,
        max_jitter=max_jitter,
        similarity_method=similarity_method,
        seed=seed,
        min_consecutive_rows=min_consecutive_rows,
        chunk_size=chunk_size,
        angle=angle,
        upscale_factor=upscale_factor,
    )

    return context.process()


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
  
  # 45度角损坏，使用2倍放大提高精度
  %(prog)s input.jpg output.jpg --angle 45 --upscale-factor 2
  
  # 垂直向下损坏（90度）
  %(prog)s input.jpg output.jpg --angle 90
  
  # 任意角度损坏，不放大（默认）
  %(prog)s input.jpg output.jpg --angle 30
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
        help="最小连续行数。一旦某行被损坏，下面n-1行也跟着被损坏。默认: 1",
    )

    parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        type=int,
        default=1,
        help="最多一次处理的行数。将连续的多行视为一个块处理，使用第一行的像素数据。默认: 1",
    )

    parser.add_argument(
        "-a",
        "--angle",
        type=float,
        default=0.0,
        help="损坏方向的角度（度数）。0度表示水平向右，90度表示垂直向下。默认: 0.0",
    )

    parser.add_argument(
        "-u",
        "--upscale-factor",
        type=int,
        default=1,
        help="放大因子。在旋转前放大图像以提高精度，处理后再缩小。值越大精度越高但速度越慢。默认: 1（不放大）",
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
    if args.upscale_factor < 1:
        parser.error("放大因子必须大于等于1")

    # 执行
    with Image.open(args.input) as input_image, (
        Image.open(args.mask_path) if args.mask_path else contextlib.nullcontext()
    ) as mask_image:
        result_image: Image.Image = pixel_sort_corruption(
            image=input_image,
            mask=mask_image if args.mask_path else None,
            corruption_ratio=args.corruption_ratio,
            max_jitter=args.max_jitter,
            similarity_method=args.similarity_method,
            seed=args.seed,
            min_consecutive_rows=args.min_consecutive_rows,
            chunk_size=args.chunk_size,
            angle=args.angle,
            upscale_factor=args.upscale_factor,
        )

    # 保存结果
    result_image.save(args.output, quality=95)
    _LOGGER.info(f"处理成功完成! 结果保存至: {args.output}")


if __name__ == "__main__":
    main()
