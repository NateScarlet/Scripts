import gradio as gr
import gradio.themes
from pixel_sort_corruption import pixel_sort_corruption
from typing import Optional, Dict, Any, Tuple
from PIL import Image as PILImage
import random


def gradio_pixel_sort_corruption(
    input_image: Optional[PILImage.Image],
    mask_image: Optional[PILImage.Image] = None,
    corruption_ratio: float = 0.3,
    max_jitter: int = 15,
    similarity_method: str = "euclidean",
    seed: int = -1,
    use_mask: bool = False,
    min_consecutive_rows: int = 1,
    chunk_size: int = 1,
) -> Tuple[Optional[PILImage.Image], int]:
    """
    Gradio包装函数，处理图像输入输出

    参数:
        input_image: 输入PIL图像
        mask_image: 蒙版图像
        corruption_ratio: 损坏比例
        max_jitter: 最大抖动范围
        similarity_method: 相似度计算方法
        seed: 随机种子
        use_mask: 是否使用蒙版
        min_consecutive_rows: 最小连续行数
        chunk_size: 一次处理的行数

    返回:
        元组: (处理后的PIL图像, 实际使用的种子)
    """
    try:
        if input_image is None:
            raise ValueError("请上传输入图片")

        # 转换PIL图像为RGB模式（确保兼容性）
        if hasattr(input_image, "mode") and input_image.mode != "RGB":
            input_image = input_image.convert("RGB")

        # 处理随机种子
        actual_seed = seed if seed != -1 else random.randint(0, 2**31 - 1)

        # 处理蒙版图像 - 检查mask_image是否是字典（Gradio隐藏组件的默认值）
        mask: Optional[PILImage.Image] = None
        if use_mask and mask_image is not None and not isinstance(mask_image, dict):
            if hasattr(mask_image, "mode") and mask_image.mode != "L":
                mask_image = mask_image.convert("L")
            mask = mask_image

        # 调用处理函数
        result_img: PILImage.Image = pixel_sort_corruption(
            image=input_image,
            mask=mask,
            corruption_ratio=corruption_ratio,
            max_jitter=max_jitter,
            similarity_method=similarity_method,
            seed=actual_seed,
            min_consecutive_rows=min_consecutive_rows,
            chunk_size=chunk_size,
        )

        return result_img, actual_seed

    except Exception as e:
        raise gr.Error(str(e))


def update_parameters_based_on_image(
    input_image: Optional[PILImage.Image],
):
    """
    根据上传的图像尺寸更新参数范围

    参数:
        input_image: 上传的PIL图像

    返回:
        包含更新后参数值的字典
    """
    if input_image is None:
        # 如果没有图像，无操作
        return

    # 获取图像尺寸
    width, height = input_image.size

    return [
        gr.update(
            maximum=width,
        ),
        gr.update(
            maximum=height,
        ),
        gr.update(
            maximum=height,
        ),
    ]


def toggle_mask_visibility(use_mask: bool) -> Dict[str, Any]:
    """
    切换蒙版可见性

    参数:
        use_mask: 是否使用蒙版

    返回:
        更新后的组件属性字典
    """
    return gr.update(visible=use_mask)


def copy_seed_to_input(seed_value: str) -> int:
    """
    将输出种子值复制到输入参数

    参数:
        seed_value: 种子值字符串

    返回:
        种子整数值
    """
    try:
        # 尝试将种子值转换为整数
        if seed_value and seed_value.isdigit():
            return int(seed_value)
        else:
            return -1  # 如果种子值无效，返回-1（随机种子）
    except (ValueError, AttributeError):
        return -1


def create_demo() -> gr.Blocks:
    """
    创建Gradio演示界面

    返回:
        配置好的Gradio Blocks实例
    """
    with gr.Blocks(
        title="高级像素排序损坏效果演示",
        theme=gradio.themes.Soft(),
    ) as demo:
        gr.Markdown(
            """
        # 🎨 高级像素排序损坏效果演示
        
        基于相似度的像素排序损坏效果，支持蒙版控制和多种相似度计算方法。
        """
        )

        with gr.Row():
            with gr.Column():
                # 输入图像
                input_image: gr.Image = gr.Image(
                    label="输入图片",
                    type="pil",
                    height=300,
                )

                # 蒙版控制
                use_mask_checkbox: gr.Checkbox = gr.Checkbox(
                    label="使用蒙版", value=False, info="启用后使用蒙版确定处理区域"
                )

                mask_image: gr.Image = gr.Image(
                    label="蒙版图片（可选）",
                    type="pil",
                    height=200,
                    visible=False,
                    value=None,
                )

                # 参数设置
                with gr.Accordion("参数设置", open=True):
                    corruption_ratio: gr.Slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.5,
                        label="损坏比例",
                        info="0-1之间，表示要处理的行比例",
                    )

                    max_jitter: gr.Slider = gr.Slider(
                        minimum=0,
                        value=15,
                        step=1,
                        label="最大抖动范围",
                        info="起始点水平抖动的最大像素范围",
                    )

                    similarity_method: gr.Dropdown = gr.Dropdown(
                        choices=["euclidean", "manhattan", "brightness"],
                        value="euclidean",
                        label="相似度计算方法",
                        info="选择像素相似度的计算方式",
                    )

                    seed: gr.Number = gr.Number(
                        value=-1,
                        label="随机种子",
                        info="-1表示使用随机种子，其他数值确保结果可重现",
                        precision=0,
                    )

                    min_consecutive_rows: gr.Slider = gr.Slider(
                        minimum=1,
                        value=1,
                        step=1,
                        label="最小连续行数",
                        info="一旦选中某行，必须连续处理下面n-1行",
                    )

                    chunk_size: gr.Slider = gr.Slider(
                        minimum=1,
                        value=1,
                        step=1,
                        label="块大小",
                        info="一次处理的行数，将多行视为一个块处理",
                    )

                # 处理按钮
                process_btn: gr.Button = gr.Button(
                    "🚀 应用像素排序效果", variant="primary", size="lg"
                )

            with gr.Column():
                # 输出图像和种子信息
                output_image: gr.Image = gr.Image(
                    label="处理结果", type="pil", height=400, show_download_button=True
                )
                seed_display = gr.Textbox(
                    label="🎲 本次处理使用的随机种子",
                    value="等待处理...",
                    interactive=False,
                    scale=4,
                )
                copy_seed_btn = gr.Button(
                    "📋 使用此种子",
                    size="sm",
                    scale=1,
                )

        # 事件处理
        # 上传图片时更新参数范围
        input_image.upload(
            fn=update_parameters_based_on_image,
            inputs=input_image,
            outputs=[max_jitter, min_consecutive_rows, chunk_size],
        )

        # 蒙版可见性控制
        use_mask_checkbox.change(
            fn=toggle_mask_visibility, inputs=use_mask_checkbox, outputs=mask_image
        )

        # 处理按钮点击事件 - 现在返回两个输出
        process_btn.click(
            fn=gradio_pixel_sort_corruption,
            inputs=[
                input_image,
                mask_image,
                corruption_ratio,
                max_jitter,
                similarity_method,
                seed,
                use_mask_checkbox,
                min_consecutive_rows,
                chunk_size,
            ],
            outputs=[output_image, seed_display],
        )

        # 添加种子复制功能
        copy_seed_btn.click(
            fn=copy_seed_to_input,
            inputs=seed_display,
            outputs=seed,
        )

        # 添加使用说明
        with gr.Accordion("使用说明", open=False):
            gr.Markdown(
                """\
### 基本用法
1. 上传输入图片（参数范围会自动根据图片尺寸调整）
2. 选择是否使用蒙版模式
3. 调整参数设置
4. 点击"应用像素排序效果"按钮
5. 查看处理结果和使用的随机种子

### 智能参数调整
- **最大抖动范围**：会根据图片宽度自动调整上限，避免超出图片边界
- **块大小**：会根据图片高度自动调整上限，确保处理效果合理
- 上传不同尺寸的图片时，参数范围会自动优化

### 蒙版模式
- 启用"使用蒙版"后上传蒙版图片
- 蒙版用于确定每行的起始位置
- 每行的起始位置由蒙版中该行最左侧非黑色像素的位置决定
- 蒙版图片会自动调整到与输入图片相同尺寸

### 无蒙版模式
- 随机选择一定比例的行进行处理
- 起始位置基于上一行的位置加上随机抖动
- 损坏比例参数控制被处理的行数

### 种子功能
- 固定随机种子可以获得可重现的效果
- 每次处理后会显示实际使用的种子值
- 种子值为-1时使用随机种子
"""
            )

    return demo


def main() -> None:
    """
    主函数：启动Gradio演示界面
    """
    # 启动Gradio界面
    demo: gr.Blocks = create_demo()
    demo.launch(
        server_port=7860,
        share=False,
        show_error=True,
    )


# 启动演示
if __name__ == "__main__":
    main()
